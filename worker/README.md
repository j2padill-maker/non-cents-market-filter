# Watchlist sync — setup

Makes your phone and laptop share one watchlist. Add a ticker on either, and it
shows up on the other within about 25 seconds.

**Why this is needed:** browser `localStorage` is private to one browser on one
device. A static site on GitHub Pages can't write to itself, so there is no way
to share state between your devices without something server-side. This Worker
is that something — it holds the canonical list in Cloudflare KV.

Free tier covers this comfortably (100,000 reads and 1,000 writes per day; this
uses a handful).

---

## 1. Create the KV namespace

Cloudflare dashboard → **Storage & Databases → KV** → **Create namespace**.

Name it `NONCENTS_WATCHLIST`. The name is yours; the *binding* name in step 3 is
what has to match exactly.

## 2. Create the Worker

**Workers & Pages → Create → Start with Hello World → Deploy.**

Name it something like `noncents-sync`. Then **Edit code**, delete what's there,
paste the contents of `watchlist-worker.js`, and **Deploy**.

Before deploying, check `ALLOWED_ORIGINS` near the top of that file. It should
list the domains your app is served from. `noncentsmarket.com` and the
`github.io` fallback are already there. Any origin not on the list is refused —
that list is what stops an arbitrary web page from reading your lists.

## 3. Bind the KV namespace

Worker → **Settings → Bindings → Add → KV namespace**.

- **Variable name:** `WATCHLIST_KV`  ← must be exactly this
- **KV namespace:** the one from step 1

## 4. Set the sync key

Worker → **Settings** → **Runtime variables and secrets** → **+ Add variable**.

In the "Add environment variable" dialog:

- **Key:** `SYNC_KEY`  ← must be exactly this
- **Value:** a long random passphrase
- **Tick the `Secret` checkbox** to the right of the Value field. (There is no
  "type" dropdown — the checkbox is what makes it a secret rather than a plain
  variable.)
- The blue button changes from "Add 0 variables" to "Add 1 variable" — click it
- Then **Deploy** to apply

Once saved as a secret the value is write-only: you can overwrite it but never
read it back. Save the key somewhere you can reach from your phone first.

Generate one rather than inventing it. In Command Prompt:

```
powershell -Command "[Convert]::ToBase64String((1..24|%{Get-Random -Max 256}))"
```

Save it somewhere you can get at from your phone — you'll type it into each
device once.

> This is a shared passphrase, not per-user authentication. It stops the
> endpoint being world-writable, which is the proportionate bar for a personal
> watchlist. Don't reuse a password you care about, and don't put anything
> sensitive in list names.

## 5. Point the app at the Worker

Copy the Worker URL (looks like `https://noncents-sync.<yourname>.workers.dev`)
into `data/sync-config.json`:

```json
{ "url": "https://noncents-sync.yourname.workers.dev" }
```

No trailing slash. Then commit and push:

```
cd /d C:\non-cents && git add data/sync-config.json && git commit -m "Point app at sync worker" && git push origin main
```

## 6. Connect each device

Open the app → **Watchlists** tab. The pill in the list bar reads
**🔑 Connect sync**. Click it, paste the `SYNC_KEY`, done. Repeat on the phone.

The first device to connect uploads its existing lists. Devices connecting after
that **merge** — every list and every ticker from both sides is kept.

## 7. Let the nightly fetch see it

So the fetch job pulls from sync rather than a stale file, set `SYNC_KEY` where
the job runs.

**Locally** (one time, then reopen Command Prompt):

```
setx SYNC_KEY "your-key-here"
```

**GitHub Actions:** repo → Settings → Secrets and variables → Actions → New
repository secret, named `SYNC_KEY`. Then add it to the fetch step in
`.github/workflows/fetch.yml` alongside the Finnhub key:

```yaml
        env:
          FINNHUB_API_KEY: ${{ secrets.FINNHUB_API_KEY }}
          SYNC_KEY: ${{ secrets.SYNC_KEY }}
```

If `SYNC_KEY` isn't set, the run falls back to `data/watchlist.json` and says so
in the log. Nothing breaks; it just won't see edits made on your phone.

---

## Checking it works

```
curl https://noncents-sync.yourname.workers.dev/health
```

Expect `{"ok":true}`. Then with your key:

```
curl -H "X-Sync-Key: your-key-here" https://noncents-sync.yourname.workers.dev/watchlist
```

Expect your lists as JSON.

## Behaviour worth knowing

**Conflicts merge, they don't overwrite.** If both devices change things while
one is offline, the result is the union — every list name and every ticker from
both. The trade: a ticker deleted on one device while the other was offline can
reappear. That's deliberate. Silently losing a ticker you just added is worse
than an unwanted one you can delete again.

**KV is eventually consistent.** A write is usually visible everywhere in a few
seconds, occasionally up to a minute. Combined with the 25-second poll, expect
changes to land on the other device inside about half a minute.

**Sync never blocks you.** If the Worker is down or the key is wrong, the pill
turns red and the app keeps working exactly as it did before — local lists plus
manual export. Nothing you type is lost.

## Later: the same Worker can hold your Finnhub key

Your spec flags API-key exposure as the reason the front end can't call Finnhub
directly. A Worker is the standard answer: it holds the key as a secret and
proxies the calls, so the browser never sees it. Adding a `/quote` route here
would let the app do live lookups instead of reading a nightly cache.
