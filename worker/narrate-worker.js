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
 *   Var     GEMINI_MODEL     optional — defaults to gemini-3.6-flash. Set this
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
// gemini-2.5-flash was retired for new users (Sept 2026); Google's API points
// callers to gemini-3.6-flash. Model IDs churn — override with the GEMINI_MODEL
// env var (e.g. gemini-3.7-flash) to move without a code change.
const DEFAULT_MODEL = 'gemini-3.6-flash';
// TTS is a separate model family. Override with GEMINI_TTS_MODEL / GEMINI_TTS_VOICE
// env vars to move models or change the voice without a code change.
const DEFAULT_TTS_MODEL = 'gemini-3.1-flash-tts-preview';
const DEFAULT_TTS_VOICE = 'Kore';

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
    // Give the model each article's headline AND its short summary (not just the
    // headline) so it can actually summarize the news, not just name it.
    lines.push('Recent news (headline — summary):\n  - ' + news.map(n => {
      const src = n.source ? ` [${n.source}]` : '';
      const sum = (n.summary || '').trim().replace(/\s+/g, ' ').slice(0, 220);
      return `${(n.headline || '').trim()}${src}${sum ? ' — ' + sum : ''}`;
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
    'Write a spoken-style briefing (about 150-220 words) that a busy investor could listen to. It MUST cover all of the sections below, in order:',
    '1) Open by naming the ticker and stating the as-of date and session of this briefing (e.g. "As of the September 1st close…"). Always state the date.',
    '2) The price move for the day (and the week if given).',
    '3) The technical read: what the indicators collectively suggest about momentum, trend, and volatility — reference the specific ones that stand out (for example RSI, MACD, distance from the 52-week low/high, price versus the 200-day average), in plain English.',
    '4) The news: summarize what the recent headlines are about, grouping related ones into themes rather than listing them one by one; and note any recent SEC filing, calling out if the company just reported (a 10-Q, 10-K, or 8-K). If there is no meaningful company-specific news, say so briefly.',
    'Rules:',
    '- Cover every section above even if briefly. Do not stop after the price — the indicators and the news are the point of the briefing.',
    '- Neutral and factual. Describe what the numbers and headlines show; do NOT tell the user to buy, sell, or hold, and do not predict prices.',
    '- No hype, no emoji, no headers, no bullet points, no markdown. Plain flowing sentences only, ready to read aloud.',
    '- Use only the facts below. Do not invent numbers, ratings, headlines, or events; summarize only the news provided.',
    '- Some items may be generic market roundups that only mention the ticker in passing — focus the news summary on items genuinely about the company, and don\'t overstate a passing mention.',
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

/* Thinking models share maxOutputTokens between hidden reasoning and the visible
   answer, so a small cap gets the answer truncated after a few words (exactly the
   "only the closing price" bug). Minimize thinking AND give a generous cap.
   Gemini 3.x flash uses thinkingLevel (can't fully disable → "low"); Gemini 2.5
   uses thinkingBudget:0. Keep both so swapping GEMINI_MODEL still behaves. */
function thinkingConfigFor(model) {
  const m = (model || '').toLowerCase();
  if (/gemini-2\.5/.test(m)) return { thinkingBudget: 0 };
  return { thinkingLevel: 'low' };
}

async function callGemini(env, prompt, maxTokens) {
  const model = (env.GEMINI_MODEL || DEFAULT_MODEL).trim();
  const url = `${GEMINI_BASE}/${encodeURIComponent(model)}:generateContent`;
  // Headroom for reasoning + the ~200-word answer. Only tokens actually
  // generated are billed, and thinkingLevel:low keeps reasoning small.
  const baseGen = { temperature: 0.4, maxOutputTokens: maxTokens || 2048, topP: 0.9 };
  const call = (gen) => fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-goog-api-key': env.GEMINI_API_KEY },
    body: JSON.stringify({ contents: [{ role: 'user', parts: [{ text: prompt }] }], generationConfig: gen }),
  });

  let res = await call({ ...baseGen, thinkingConfig: thinkingConfigFor(model) });
  let raw = await res.text();
  let data = null;
  try { data = JSON.parse(raw); } catch { /* non-JSON error body */ }

  // Self-heal: if a model rejects the thinking config (field/value churn),
  // retry once without it — the big maxOutputTokens alone avoids the truncation.
  if (!res.ok && /think/i.test((data && data.error && data.error.message) || raw || '')) {
    res = await call(baseGen);
    raw = await res.text();
    data = null;
    try { data = JSON.parse(raw); } catch { /* non-JSON */ }
  }

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

/* ── Gemini TTS ──────────────────────────────────────────────────────────────
   Gemini returns raw PCM (24 kHz, 16-bit, mono) as base64 — not a playable
   container. We wrap it in a 44-byte WAV header here so the browser can play
   the bytes directly with no client-side decoding. */

function base64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function rateFromMime(mime) {
  const m = /rate=(\d+)/.exec(mime || '');
  return m ? parseInt(m[1], 10) : 24000;   // Gemini TTS default is 24 kHz
}

function pcmToWav(pcm, sampleRate, channels, bits) {
  const blockAlign = channels * (bits / 8);
  const byteRate = sampleRate * blockAlign;
  const dataLen = pcm.length;
  const buf = new ArrayBuffer(44 + dataLen);
  const view = new DataView(buf);
  const put = (off, str) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)); };
  put(0, 'RIFF'); view.setUint32(4, 36 + dataLen, true); put(8, 'WAVE');
  put(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);      // PCM
  view.setUint16(22, channels, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true); view.setUint16(32, blockAlign, true); view.setUint16(34, bits, true);
  put(36, 'data'); view.setUint32(40, dataLen, true);
  new Uint8Array(buf, 44).set(pcm);
  return new Uint8Array(buf);
}

async function callGeminiTTS(env, text) {
  const model = (env.GEMINI_TTS_MODEL || DEFAULT_TTS_MODEL).trim();
  const voice = (env.GEMINI_TTS_VOICE || DEFAULT_TTS_VOICE).trim();
  const url = `${GEMINI_BASE}/${encodeURIComponent(model)}:generateContent`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-goog-api-key': env.GEMINI_API_KEY },
    body: JSON.stringify({
      contents: [{ parts: [{ text }] }],
      generationConfig: {
        responseModalities: ['AUDIO'],
        speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: voice } } },
      },
    }),
  });

  const raw = await res.text();
  let data = null;
  try { data = JSON.parse(raw); } catch { /* non-JSON error body */ }

  if (!res.ok) {
    const msg = (data && data.error && data.error.message) || raw.slice(0, 300) || 'Gemini TTS request failed';
    const err = new Error(msg);
    err.upstreamStatus = res.status;
    throw err;
  }

  const cand = data && Array.isArray(data.candidates) ? data.candidates[0] : null;
  const parts = cand && cand.content && Array.isArray(cand.content.parts) ? cand.content.parts : [];
  const audioPart = parts.find(p => p && p.inlineData && p.inlineData.data);
  if (!audioPart) {
    const reason = cand && cand.finishReason ? ` (finishReason: ${cand.finishReason})` : '';
    const err = new Error('Gemini TTS returned no audio' + reason);
    err.upstreamStatus = 502;
    throw err;
  }
  const pcm = base64ToBytes(audioPart.inlineData.data);
  const rate = rateFromMime(audioPart.inlineData.mimeType);
  return pcmToWav(pcm, rate, 1, 16);   // mono, 16-bit
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
      ttsModel: (env.GEMINI_TTS_MODEL || DEFAULT_TTS_MODEL).trim(),
      ttsVoice: (env.GEMINI_TTS_VOICE || DEFAULT_TTS_VOICE).trim(),
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

  // /tts speaks the already-generated narration text (so the audio matches what
  // the user is reading and we don't regenerate it). Falls back to narrating the
  // briefing if only that is sent. Returns a playable WAV, not JSON.
  if (url.pathname === '/tts') {
    let text = String((body && body.text) || '').trim();
    if (!text && body && body.briefing && body.briefing.ticker) {
      text = await callGemini(env, narratePrompt(body.briefing), 2048);
    }
    text = text.slice(0, 1600);
    if (!text) return json({ error: 'Missing text to speak.' }, 400, request);
    const wav = await callGeminiTTS(env, text);
    return new Response(wav, {
      status: 200,
      headers: { 'Content-Type': 'audio/wav', 'Cache-Control': 'no-store', ...corsHeaders(request) },
    });
  }

  const b = body && body.briefing;
  if (!b || typeof b !== 'object' || !b.ticker) {
    return json({ error: 'Missing briefing object.' }, 400, request);
  }

  if (url.pathname === '/narrate') {
    const script = await callGemini(env, narratePrompt(b), 2048);
    return json({ ticker: b.ticker, script, disclaimer: DISCLAIMER }, 200, request);
  }

  if (url.pathname === '/dig') {
    const question = String((body.question || '')).trim().slice(0, 500);
    if (!question) return json({ error: 'Missing question.' }, 400, request);
    const answer = await callGemini(env, digPrompt(b, question), 1024);
    return json({ ticker: b.ticker, answer, disclaimer: DISCLAIMER }, 200, request);
  }

  return json({ error: 'Not found.' }, 404, request);
}
