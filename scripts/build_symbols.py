"""
Build data/symbols.json — a compact, searchable index of tradable US symbols.

Why this exists
---------------
The front-end must never call Finnhub directly (the API key would be exposed on
a public GitHub Pages site). But without a lookup, adding a ticker to a
watchlist is blind: a typo and a real-but-thinly-covered symbol look identical
until a full fetch finishes 30 minutes later.

So we do the lookup once, server-side, and ship the answer as a static file the
browser can search instantly — by ticker OR by company name — with no key and
no network round trip.

Format (arrays, not objects — roughly a third the size at this row count):
    {
      "generated": "2026-08-28T...",
      "count": 11234,
      "types": ["Common Stock", "ADR", "ETP", ...],
      "symbols": [["MDB", "MongoDB Inc", 0], ...]     # [ticker, name, typeIndex]
    }

Usage:
    python scripts/build_symbols.py            # writes data/symbols.json
Requires FINNHUB_API_KEY in the environment. Costs a single API call.
"""

import os
import json
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
BASE_URL = "https://finnhub.io/api/v1"
SYMBOLS_FILE = "data/symbols.json"

# Finnhub's US exchange covers NYSE/NASDAQ/AMEX plus a large body of OTC
# symbols, which is where foreign ordinaries and ADRs (TOELF, HSYDF) live.
EXCHANGES = ["US"]

# Symbol types worth keeping. Finnhub returns a long tail of warrants, rights,
# units and preferreds that only add noise to an autocomplete.
KEEP_TYPES = {
    "Common Stock", "ADR", "GDR", "REIT", "ETP", "Unit",
    "Equity", "Foreign Sh.", "NY Reg Shrs", "Ltd Part", "",
}


def fetch_symbols(exchange):
    url = f"{BASE_URL}/stock/symbol"
    for attempt in range(3):
        try:
            r = requests.get(url, params={"exchange": exchange, "token": FINNHUB_KEY},
                             timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                print("  Rate limited, waiting 20s...")
                time.sleep(20)
                continue
            print(f"  HTTP {r.status_code} for exchange {exchange}")
            return []
        except Exception as e:
            print(f"  Request error: {e}")
            time.sleep(3)
    return []


def main():
    if not FINNHUB_KEY:
        raise SystemExit("✗ FINNHUB_API_KEY is not set — cannot build the symbol index.")

    print("Building symbol index...")
    rows = []
    for ex in EXCHANGES:
        print(f"  Fetching {ex} symbols...")
        data = fetch_symbols(ex)
        print(f"    {len(data)} raw symbols")
        rows.extend(data)

    if not rows:
        raise SystemExit("✗ No symbols returned — leaving any existing index alone.")

    types = []
    type_index = {}
    seen = set()
    out = []

    for item in rows:
        sym = (item.get("symbol") or "").strip().upper()
        name = (item.get("description") or "").strip()
        stype = (item.get("type") or "").strip()

        if not sym or sym in seen:
            continue
        if stype and stype not in KEEP_TYPES:
            continue
        # Finnhub returns some symbols with characters that can't be queried
        # back through /quote; drop them rather than offer a dead suggestion.
        if any(c in sym for c in " /^"):
            continue

        seen.add(sym)
        if stype not in type_index:
            type_index[stype] = len(types)
            types.append(stype)
        # Long names bloat the file and get truncated in the UI anyway.
        out.append([sym, name[:60], type_index[stype]])

    out.sort(key=lambda r: r[0])

    os.makedirs("data", exist_ok=True)
    payload = {
        "generated": datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(),
        "count": len(out),
        "types": types,
        "symbols": out,
    }
    # Separators matter here: the default ", " / ": " padding adds ~15% to a
    # file this repetitive.
    with open(SYMBOLS_FILE, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_kb = os.path.getsize(SYMBOLS_FILE) / 1024
    print(f"\n✓ {len(out)} symbols written to {SYMBOLS_FILE} ({size_kb:.0f} KB)")
    print(f"✓ {len(types)} symbol types: {', '.join(t or '(none)' for t in types[:8])}")


if __name__ == "__main__":
    main()
