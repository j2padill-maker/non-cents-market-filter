/**
 * Non-Cents narration Worker  (Phase 3 — Gemini)
 * ------------------------------------------------------------------
 * Proxies Google's Gemini API so the API key never touches the browser or the
 * repo. Two jobs:
 *
 *   POST /narrate  ->  a short, plain-English spoken-style briefing built from
 *                      one stock's briefing JSON. This is what the 📄 doc modal
 *                      shows, and what the Phase-4 audio step will read aloud.
 *   POST /dig      ->  answers a follow-up question about that same stock, so
 *                      the initial briefing can stay short and the user can ask
 *                      for more on any thread on demand.
 *
 * Sibling of worker/watchlist-worker.js and follows the same conventions:
 * origin allowlist, everything wrapped so an error still returns JSON WITH CORS
 * headers, and a self-diagnosing /health that never reveals a secret.
 *
 * Bindings
 *   Secret  GEMINI_API_KEY   required — from aistudio.google.com (free tier).
 *   Var     GEMINI_MODEL     optional — defaults to gemini-2.5-flash. Set this
 *                            to switch models without a code change (model
 *                            names churn; the endpoint shape does not).
 *   Secret  NARRATE_KEY      optional — if set, every /narrate and /dig call
 *                            must send a matching  X-Sync-Key  header. Set it to
 *                            the SAME value as the watchlist Worker's SYNC_KEY
 *                            and the app reuses the key it already stores, so
 *                            there's no second key to enter. Leave it unset to
 *                            rely on the origin allowlist alone.
 *
 * Cost: Gemini's free tier. Nothing is generated until a user actually opens a
 * briefing (the browser caches the result for the session), so idle cost is $0.
 */

// Endpoint shape is stable across model releases; the model ID is a variable.
const GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta/models';
const DEFAULT_MODEL = 'gemini-2.5-flash';

// Same allowlist as the watchlist Worker. A wildcard here would let any page on
// the internet spend your Gemini quota.
const ALLOWED_ORIGINS = [
  'https://noncentsmarket.com',
  'https://www.noncentsmarket.com',
  'https://j2padill-maker.github.io',
  'http://localhost:8000',
  'http://127.0.0.1:8000',
];

function corsHeaders(request) {
  const origin = request.headers.get('Origin') || '';
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allowed,
    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Sync-Key',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

function json(body, status, request) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(request) },
  });
}

const DISCLAIMER = 'Informational only. Not financial advice.';

/* ── Prompt building ─────────────────────────────────────────────────────
   The Worker owns the prompts so narration can be tuned by redeploying the
   Worker alone, without touching the site. The briefing JSON is distilled into
   a compact fact block — never the raw object — so the model gets clean inputs
   and the token count stays small. */

function fmtPct(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return null;
  return (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%';
}

function factBlock(b) {
  const lines = [];
  const p = b.price || {};
  lines.push(`Ticker: ${b.ticker || '?'}`);
  if (b.data_asof) lines.push(`As of: ${b.data_asof} (${(b.session || '').toUpperCase()} briefing)`);
  if (p.last != null) lines.push(`Last price: $${Number(p.last).toFixed(2)}`);
  const moves = [];
  if (p.move_day_pct != null) moves.push(`day ${fmtPct(p.move_day_pct)}`);
  if (p.move_open_close_pct != null) moves.push(`open->close ${fmtPct(p.move_open_close_pct)}`);
  if (p.move_week_pct != null) moves.push(`week ${fmtPct(p.move_week_pct)}`);
  if (moves.length) lines.push(`Moves: ${moves.join(', ')}`);

  const io = b.indicators || {};
  const ind = [];
  const push = (label, val, read) => {
    if (val === null || val === undefined) { if (read) ind.push(`${label}: ${read}`); return; }
    ind.push(`${label}: ${val}${read ? ' — ' + read : ''}`);
  };
  if (io.rsi14) push('RSI(14)', io.rsi14.value, io.rsi14.read);
  if (io.macd) push('MACD', io.macd.macd != null ? Number(io.macd.macd).toFixed(2) : null, io.macd.read);
  if (io.bollinger_pctb) push('Bollinger %B', io.bollinger_pctb.pctb, io.bollinger_pctb.read);
  if (io.pct_from_52w_low) push('% from 52wk low', io.pct_from_52w_low.value != null ? io.pct_from_52w_low.value + '%' : null, io.pct_from_52w_low.read);
  if (io.pct_from_52w_high) push('% from 52wk high', io.pct_from_52w_high.value != null ? io.pct_from_52w_high.value + '%' : null, io.pct_from_52w_high.read);
  if (io.price_vs_ma200) push('Price vs 200-day MA', io.price_vs_ma200.pct != null ? io.price_vs_ma200.pct + '%' : null, io.price_vs_ma200.read);
  if (io.atr14) push('ATR(14)', io.atr14.value != null ? io.atr14.value + ' (' + io.atr14.pct_of_price + '% of price)' : null, io.atr14.read);
  if (io.rel_volume) push('Relative volume', io.rel_volume.value != null ? io.rel_volume.value + 'x' : null, io.rel_volume.read);
  if (io.mfi14) push('Money Flow Index', io.mfi14.value, io.mfi14.read);
  if (ind.length) lines.push('Indicators:\n  - ' + ind.join('\n  - '));

  const news = Array.isArray(b.news) ? b.news.slice(0, 6) : [];
  if (news.length) {
    lines.push('Recent headlines:\n  - ' + news.map(n => {
      const src = n.source ? ` (${n.source})` : '';
      return `${(n.headline || '').trim()}${src}`;
    }).join('\n  - '));
  }
  const filings = Array.isArray(b.filings) ? b.filings.slice(0, 4) : [];
  if (filings.length) {
    lines.push('Recent SEC filings:\n  - ' + filings.map(f =>
      `${f.form || ''} ${f.title ? '(' + f.title + ')' : ''} ${f.date || ''}`.trim()
    ).join('\n  - '));
  }
  return lines.join('\n');
}

function narratePrompt(b) {
  return [
    'You are a concise market-briefing writer for a personal stock-screener app.',
    'Write a short spoken-style briefing (about 90-130 words, 3-5 sentences) that a busy investor could listen to.',
    'Cover, in plain English: the day\'s price move, what the technical indicators collectively suggest (momentum, trend, volatility), and the single most relevant news thread if any stands out.',
    'Rules:',
    '- Neutral and factual. Describe what the numbers show; do NOT tell the user to buy, sell, or hold, and do not predict prices.',
    '- No hype, no emoji, no headers, no bullet points, no markdown. Plain sentences only, ready to read aloud.',
    '- Use only the facts below. Do not invent numbers, ratings, or events.',
    '- Refer to the company by its ticker.',
    '',
    'FACTS:',
    factBlock(b),
  ].join('\n');
}

function digPrompt(b, question) {
  return [
    'You are a concise market-briefing assistant for a personal stock-screener app.',
    'The user has read a short briefing on this stock and wants to dig deeper on one point.',
    'Answer their question in 2-4 short plain-English sentences.',
    'Rules:',
    '- Neutral and factual. Explain what the data shows or what an indicator/term means. Do NOT give buy/sell/hold advice or price predictions.',
    '- Prefer the facts below. You may briefly explain what a named indicator generally measures, but do not invent numbers, ratings, headlines, or events for this company.',
    '- If the answer isn\'t in the facts and isn\'t general market knowledge, say so plainly.',
    '- No markdown, no headers, no bullet points. Plain sentences.',
    '',
    'FACTS:',
    factBlock(b),
    '',
    'USER QUESTION: ' + question,
  ].join('\n');
}

/* ── Gemini call ─────────────────────────────────────────────────────────── */

async function callGemini(env, prompt, maxTokens) {
  const model = (env.GEMINI_MODEL || DEFAULT_MODEL).trim();
  const url = `${GEMINI_BASE}/${encodeURIComponent(model)}:generateContent`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-goog-api-key': env.GEMINI_API_KEY,
    },
    body: JSON.stringify({
      contents: [{ role: 'user', parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.4,
        maxOutputTokens: maxTokens || 320,
        topP: 0.9,
      },
    }),
  });

  const raw = await res.text();
  let data = null;
  try { data = JSON.parse(raw); } catch { /* non-JSON error body */ }

  if (!res.ok) {
    const msg = (data && data.error && data.error.message) || raw.slice(0, 300) || 'Gemini request failed';
    const err = new Error(msg);
    err.upstreamStatus = res.status;
    throw err;
  }

  // Pull the text out of the first candidate. Guard every hop — a blocked or
  // empty response has candidates missing rather than an error status.
  const cand = data && Array.isArray(data.candidates) ? data.candidates[0] : null;
  const parts = cand && cand.content && Array.isArray(cand.content.parts) ? cand.content.parts : [];
  const text = parts.map(pt => pt && pt.text ? pt.text : '').join('').trim();
  if (!text) {
    const reason = cand && cand.finishReason ? ` (finishReason: ${cand.finishReason})` : '';
    const err = new Error('Gemini returned no text' + reason);
    err.upstreamStatus = 502;
    throw err;
  }
  return text;
}

/* ── HTTP handling ───────────────────────────────────────────────────────── */

export default {
  async fetch(request, env) {
    try {
      return await handle(request, env);
    } catch (err) {
      const status = err && err.upstreamStatus ? err.upstreamStatus : 500;
      return json(
        {
          error: 'worker_exception',
          message: String((err && err.message) || err),
          hint: /GEMINI_API_KEY|api key|API_KEY_INVALID|permission/i.test(String(err && err.message))
            ? 'Check the GEMINI_API_KEY secret. Worker -> Settings -> Variables and Secrets. Get a free key at aistudio.google.com.'
            : 'Check the Worker logs in the Cloudflare dashboard.',
        },
        status,
        request
      );
    }
  },
};

async function handle(request, env) {
  const url = new URL(request.url);

  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders(request) });
  }

  // Self-diagnosing health check — reports WHETHER each piece is wired up,
  // never what any secret contains. Safe to hit from anywhere.
  if (url.pathname === '/health') {
    const keySet = Boolean(env.GEMINI_API_KEY);
    return json({
      ok: keySet,
      keySet,
      model: (env.GEMINI_MODEL || DEFAULT_MODEL).trim(),
      gated: Boolean(env.NARRATE_KEY),
      hint: keySet
        ? 'GEMINI_API_KEY is set.'
        : 'GEMINI_API_KEY secret missing. Worker -> Settings -> Variables and Secrets. Free key: aistudio.google.com.',
    }, 200, request);
  }

  if (!env.GEMINI_API_KEY) {
    return json({ error: 'Worker misconfigured: GEMINI_API_KEY secret is not set.' }, 500, request);
  }

  // Optional shared-key gate. Only enforced when NARRATE_KEY is configured.
  if (env.NARRATE_KEY && request.headers.get('X-Sync-Key') !== env.NARRATE_KEY) {
    return json({ error: 'Bad or missing key.' }, 401, request);
  }

  if (request.method !== 'POST') {
    return json({ error: 'Method not allowed.' }, 405, request);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'Body must be JSON.' }, 400, request);
  }

  const b = body && body.briefing;
  if (!b || typeof b !== 'object' || !b.ticker) {
    return json({ error: 'Missing briefing object.' }, 400, request);
  }

  if (url.pathname === '/narrate') {
    const script = await callGemini(env, narratePrompt(b), 320);
    return json({ ticker: b.ticker, script, disclaimer: DISCLAIMER }, 200, request);
  }

  if (url.pathname === '/dig') {
    const question = String((body.question || '')).trim().slice(0, 500);
    if (!question) return json({ error: 'Missing question.' }, 400, request);
    const answer = await callGemini(env, digPrompt(b, question), 380);
    return json({ ticker: b.ticker, answer, disclaimer: DISCLAIMER }, 200, request);
  }

  return json({ error: 'Not found.' }, 404, request);
}
