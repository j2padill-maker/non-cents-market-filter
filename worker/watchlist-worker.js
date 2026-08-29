/**
 * Non-Cents watchlist sync Worker
 * ------------------------------------------------------------------
 * Holds the canonical watchlist in Cloudflare KV so the phone and the laptop
 * see the same lists. The browser reads and writes it directly; the nightly
 * fetch job reads it too, so a ticker added on the phone is fetched that night
 * without touching the repo by hand.
 *
 * Endpoints
 *   GET  /watchlist   -> { version, updated, rev, lists }
 *   PUT  /watchlist   -> body { lists, baseRev }  ->  { ok, rev, updated, lists }
 *                        409 + current state if baseRev is stale
 *   GET  /health      -> { ok: true }
 *
 * Auth
 *   Every request needs an  X-Sync-Key  header matching the SYNC_KEY secret.
 *   The key is entered once per device in the app and kept in localStorage —
 *   it is never written into the page source. This is a shared passphrase, not
 *   real per-user auth: it keeps the endpoint from being world-writable, which
 *   is the proportionate bar for a personal watchlist. Don't reuse a password
 *   you care about, and don't put anything sensitive in list names.
 *
 * Bindings required
 *   KV namespace binding:  WATCHLIST_KV
 *   Secret:                SYNC_KEY
 */

const KV_KEY = 'watchlist:v1';

// Only these origins may call the Worker from a browser. Add or remove as
// needed — a wildcard here would let any page on the internet read your lists.
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
    'Access-Control-Allow-Methods': 'GET, PUT, OPTIONS',
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

const EMPTY = { version: 1, updated: null, rev: 0, lists: [] };

/** Normalize whatever the client sent into the shape everything else expects. */
function cleanLists(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  for (const entry of raw) {
    if (!entry || typeof entry.name !== 'string') continue;
    const name = entry.name.trim().slice(0, 60);
    if (!name) continue;
    const seen = new Set();
    const tickers = [];
    for (const t of Array.isArray(entry.tickers) ? entry.tickers : []) {
      const sym = String(t).trim().toUpperCase().replace(/[^A-Z0-9.\-]/g, '');
      if (!sym || sym.length > 8 || seen.has(sym)) continue;
      seen.add(sym);
      tickers.push(sym);
      if (tickers.length >= 500) break;
    }
    out.push({ name, tickers });
    if (out.length >= 50) break;
  }
  return out;
}

async function readState(env) {
  // cacheTtl 0: KV is eventually consistent, and caching the read at the edge
  // would make a change made on the phone take even longer to reach the laptop.
  const stored = await env.WATCHLIST_KV.get(KV_KEY, { type: 'json', cacheTtl: 0 });
  return stored && typeof stored === 'object' ? { ...EMPTY, ...stored } : { ...EMPTY };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    if (url.pathname === '/health') {
      return json({ ok: true }, 200, request);
    }

    if (!env.SYNC_KEY) {
      return json({ error: 'Worker misconfigured: SYNC_KEY secret is not set.' }, 500, request);
    }
    if (request.headers.get('X-Sync-Key') !== env.SYNC_KEY) {
      return json({ error: 'Bad or missing sync key.' }, 401, request);
    }

    if (url.pathname !== '/watchlist') {
      return json({ error: 'Not found.' }, 404, request);
    }

    if (request.method === 'GET') {
      return json(await readState(env), 200, request);
    }

    if (request.method === 'PUT') {
      let body;
      try {
        body = await request.json();
      } catch {
        return json({ error: 'Body must be JSON.' }, 400, request);
      }

      const current = await readState(env);
      const baseRev = Number(body.baseRev);

      // Optimistic concurrency. If the client is writing on top of a revision
      // that is no longer current, someone else saved first — hand back the
      // current state and let the client merge rather than silently clobbering.
      if (Number.isFinite(baseRev) && baseRev !== current.rev) {
        return json(
          { error: 'conflict', message: 'The watchlist changed on another device.', ...current },
          409,
          request
        );
      }

      const next = {
        version: 1,
        updated: new Date().toISOString(),
        rev: current.rev + 1,
        lists: cleanLists(body.lists),
      };
      await env.WATCHLIST_KV.put(KV_KEY, JSON.stringify(next));
      return json({ ok: true, ...next }, 200, request);
    }

    return json({ error: 'Method not allowed.' }, 405, request);
  },
};
