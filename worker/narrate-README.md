# Non-Cents narration Worker (Phase 3 — Gemini)

`narrate-worker.js` proxies Google's Gemini API so the key never lives in the
browser or the repo. It powers two things in the Briefings 📄 doc view:

- **Narration** — a short, spoken-style plain-English briefing built from each
  stock's briefing JSON (the same text the Phase-4 audio step will read aloud).
- **Dig deeper** — answers a follow-up question about that stock on demand, so
  the initial briefing can stay short.

Sibling of `watchlist-worker.js`; same conventions (origin allowlist, errors
returned as JSON + CORS, self-diagnosing `/health`).

Nothing is generated until a briefing is actually opened, and the browser
caches the result for the session — so idle cost is **$0** and it stays inside
Gemini's free tier for personal use.

## One-time setup

### 1. Get a free Gemini API key
1. Go to <https://aistudio.google.com> → **Get API key** → **Create API key**.
2. Copy the key (starts with `AIza...`). Free tier, no billing needed.

### 2. Create the Worker
Cloudflare dashboard → **Workers & Pages** → **Create** → **Worker**. Name it
`noncents-narrate` (any name is fine). Paste the contents of
`worker/narrate-worker.js` and **Deploy**.

Or with wrangler, from `worker/`:
```
wrangler deploy narrate-worker.js --name noncents-narrate
```

### 3. Set the key (and options)
Worker → **Settings → Variables and Secrets**:

| Name              | Type   | Value                                             |
|-------------------|--------|---------------------------------------------------|
| `GEMINI_API_KEY`  | Secret | the `AIza...` key from step 1  **(required)**      |
| `GEMINI_MODEL`    | Var    | optional — defaults to `gemini-2.5-flash`. Set to another flash model (e.g. `gemini-3-flash`) to switch without code changes. |
| `NARRATE_KEY`     | Secret | optional — set it to the **same value as the watchlist Worker's `SYNC_KEY`** to require a key on every call. The app reuses the key it already stores, so there's nothing new to enter. Leave unset to rely on the origin allowlist alone. |

With wrangler:
```
wrangler secret put GEMINI_API_KEY --name noncents-narrate
```

### 4. Point the app at it
Edit `data/narrate-config.json`, set `url` to your Worker URL:
```json
{ "url": "https://noncents-narrate.j2padill.workers.dev" }
```
Commit + push. Leaving `url` blank keeps narration off — the doc view still
shows the full indicator table and news, just no AI summary.

## Check it's working
Open `https://<your-worker>.workers.dev/health` — it reports whether the key is
set and which model is selected, without revealing the key:
```json
{ "ok": true, "keySet": true, "model": "gemini-2.5-flash", "gated": false }
```

## Endpoints
| Method | Path       | Body                          | Returns                          |
|--------|------------|-------------------------------|----------------------------------|
| GET    | `/health`  | —                             | `{ ok, keySet, model, gated }`   |
| POST   | `/narrate` | `{ briefing }`                | `{ ticker, script, disclaimer }` |
| POST   | `/dig`     | `{ briefing, question }`      | `{ ticker, answer, disclaimer }` |

`briefing` is one stock's object from `data/briefings/<TICKER>.json`. The Worker
distills it into a compact fact block before prompting Gemini — it never sends
the raw object as-is, and the prompts live in the Worker so narration can be
tuned by redeploying the Worker alone.

## Cost / limits
Gemini free tier (as of 2026) is roughly 10–30 requests/min and 500–1500
requests/day depending on model — far above one person opening a handful of
briefings a day. If you ever exceed it, `/narrate` returns a `429` and the app
shows a friendly "try again shortly" note; the rest of the briefing is
unaffected.
