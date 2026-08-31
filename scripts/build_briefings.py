"""
Non-Cents — Briefing builder (Phase 1).

Downstream stage that runs AFTER the screener fetch. For each ticker on the
user's chosen source (watchlist now; portfolio in Phase 5) it pulls OHLCV from
yfinance, computes the default indicator set + price moves via indicators.py,
and writes one briefing JSON per ticker to data/briefings/, plus an index.json.

Phase 1 scope: data + indicators only. News (Phase 2), the narrated script
(Phase 3), and audio (Phase 4) attach to this same JSON later — the fields are
present as empty placeholders now so nothing downstream has to change shape.

Design notes:
  · Separate script, not bolted into fetch_data.py — keeps the battle-tested
    screener untouched. Shares indicator math through indicators.py so the two
    never diverge.
  · Every data pull goes through get_ohlcv() — the single provider seam. Swap
    yfinance for a redistribution-licensed provider there when going public.
  · An empty result never overwrites a good briefing (mirrors the screener rule).
  · Everything is keyed by user_id (default "local") — the going-public seam so
    adding auth later doesn't re-plumb storage.

Usage:
  python build_briefings.py [--session morning|close] [--tickers MDB,NVDA]
                            [--root PATH] [--user local]
"""

import os
import sys
import json
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

import indicators as ind

DISCLAIMER = "Informational only. Not financial advice."
TZ = ZoneInfo("America/Los_Angeles")


# ── provider seam ─────────────────────────────────────────────────────────────

def get_ohlcv(ticker, period="2y"):
    """The ONLY place market data is fetched. Returns an OHLCV DataFrame
    (oldest→newest) or None. Swap the body to change data providers."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        if df is None or df.empty or "Close" not in df:
            return None
        df = df.dropna(subset=["Close"])
        return df if len(df) else None
    except Exception as e:
        print(f"  yfinance error for {ticker}: {e}")
        return None


# ── source loading ────────────────────────────────────────────────────────────

def load_watchlist_tickers(root):
    path = os.path.join(root, "data", "watchlist.json")
    try:
        with open(path) as f:
            wl = json.load(f)
    except Exception as e:
        print(f"  could not read watchlist.json: {e}")
        return []
    seen, out = set(), []
    for lst in wl.get("lists", []):
        for t in lst.get("tickers", []):
            t = (t or "").strip().upper()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return out


# ── per-ticker briefing ───────────────────────────────────────────────────────

def build_one(ticker, session, user_id, selected=None):
    now = datetime.now(TZ)
    base = {
        "ticker": ticker,
        "user_id": user_id,
        "session": session,
        "generated_at": now.isoformat(),
        "disclaimer": DISCLAIMER,
        "selected_indicators": selected or ind.DEFAULT_INDICATORS,
        # placeholders for later phases so the shape never changes:
        "news": [],
        "filings": [],
        "script_text": None,
        "audio_cached": False,
    }

    MIN_BARS = 30  # need enough history for the indicators to mean anything
    df = get_ohlcv(ticker)
    if df is None or len(df) < MIN_BARS:
        base["status"] = "nodata"
        n = 0 if df is None else len(df)
        base["note"] = (f"Insufficient price history from provider ({n} bars; "
                        "thin/foreign listing or bad symbol).")
        return base

    moves = ind.price_moves(df)
    indicators, extras = ind.compute_indicators(df, selected)

    base["status"] = "ok"
    base["data_asof"] = str(df.index[-1].date())
    base["price"] = moves
    base["indicators"] = indicators
    base["low_52w"] = extras["low_52w"]
    base["high_52w"] = extras["high_52w"]
    base["ma50"] = extras["ma50"]
    base["ma200"] = extras["ma200"]
    return base


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None, help="morning|close (default: infer from time)")
    ap.add_argument("--tickers", default=None, help="comma list to override the watchlist (testing)")
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--user", default="local", help="user_id key (going-public seam)")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    session = args.session or ("morning" if datetime.now(TZ).hour < 12 else "close")

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = load_watchlist_tickers(root)

    if not tickers:
        print("✗ No tickers to brief. Nothing to do.")
        return 0

    out_dir = os.path.join(root, "data", "briefings")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Building {session} briefings for {len(tickers)} tickers: {', '.join(tickers)}")
    index = {"version": 1, "user_id": args.user, "session": session,
             "generated_at": datetime.now(TZ).isoformat(), "briefings": []}
    ok = 0
    for t in tickers:
        print(f"→ {t}")
        b = build_one(t, session, args.user)
        # never overwrite a good briefing with an empty one
        dest = os.path.join(out_dir, f"{t}.json")
        if b["status"] == "nodata" and os.path.exists(dest):
            print(f"  nodata — keeping existing briefing for {t}")
        else:
            with open(dest, "w") as f:
                json.dump(b, f, indent=2)
        if b["status"] == "ok":
            ok += 1
            p = b["price"]
            r = b["indicators"].get("rsi14", {}).get("value")
            print(f"  ${p.get('last')}  day {p.get('move_day_pct')}%  "
                  f"wk {p.get('move_week_pct')}%  RSI {r}")
        else:
            print(f"  {b['status']}: {b.get('note','')}")
        index["briefings"].append({
            "ticker": t, "status": b["status"],
            "file": f"data/briefings/{t}.json",
            "data_asof": b.get("data_asof"),
        })

    with open(os.path.join(out_dir, "index.json"), "w") as f:
        json.dump(index, f, indent=2)

    print(f"\n✓ {ok}/{len(tickers)} briefings built. Index → data/briefings/index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
