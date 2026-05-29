import os
import json
import time
import requests
from datetime import datetime

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
BASE_URL = "https://finnhub.io/api/v1"

# ── UNIVERSE ──────────────────────────────────────────────────────────────────

SECTORS = {
    "AI Hardware": [
        "NVDA", "AMD", "INTC", "MU", "AMAT", "LRCX", "AVGO", "ASML", "TSM",
        "DELL", "SMCI", "VRT", "ETN", "ATKR", "MOD", "NVT", "FORM", "COHR",
        "ATSK"
    ],
    "AI Software": [
        "NET", "DDOG", "DT", "FSLY", "CRWD", "PANW", "ZS", "SNOW", "PLTR",
        "PATH", "OKTA", "MDB", "WDAY", "FTNT", "TEAM", "NOW", "CRM"
    ],
    "Robotics": [
        "ISRG", "CGNX", "AVAV", "SYM", "PATH", "TER", "NOVT", "IPGP", "ROK",
        "ZBRA", "KEYS", "SERV", "OLL", "HSYDF", "PEGA", "JBTM", "EMR", "HON"
    ],
    "Homebuilders": [
        "DHI", "LEN", "PHM", "NVR", "TOL", "KBH", "MDC", "MHO", "TMHC",
        "BLDR", "BLD", "TREX", "OC", "MAS", "CARR", "TT", "LII", "SHW",
        "LOW", "HD"
    ],
    "Fintech": [
        "SOFI", "PYPL", "CRCL", "SQ", "XYZ", "AFRM", "UPST", "NU", "SEZL",
        "V", "MA", "AXP", "COF", "DFS", "COIN"
    ],
    "Nuclear Energy": [
        "OKLO", "SMR", "CEG", "VST", "CCJ", "LEU", "GEV", "SO", "BE",
        "NRG", "DYN", "LMT", "BWXT"
    ],
    "Drones": [
        "AVAV", "KTOS", "JOBY", "ACHR", "TXT", "NOC", "LMT", "RCAT",
        "ONDS", "UMAC", "BA", "HII"
    ],
    "Mining & Materials": [
        "VALE", "RIO", "FCX", "NEM", "GOLD", "MP", "LTHM", "ALB", "NUE",
        "AA", "X", "CLF", "STLD", "RS"
    ],
    "Energy": [
        "OXY", "DVN", "COP", "HES", "EOG", "SLB", "HAL", "MPC", "VLO",
        "PSX", "XOM", "CVX", "PXD", "FANG", "APA"
    ],
    "S&P500 Core": [
        "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "BRK.B",
        "JPM", "LLY", "UNH", "XOM", "V", "MA", "COST", "HD", "PG", "JNJ",
        "ABBV", "MRK", "CVX", "CRM", "BAC", "NFLX", "AMD", "PEP", "KO",
        "TMO", "ORCL", "ACN", "MCD", "LIN", "ABT", "CSCO", "WMT", "DHR",
        "TXN", "PM", "NEE", "ADBE", "RTX", "HON", "QCOM", "GE", "IBM",
        "AMGN", "CAT", "SPGI", "INTU", "LOW", "GS", "MS", "BLK", "AXP",
        "AMAT", "ELV", "MDT", "SYK", "ISRG", "VRTX", "GILD", "REGN",
        "ZTS", "CB", "PLD", "AMT", "SCHW", "C", "WFC", "USB", "MMC",
        "TJX", "MDLZ", "CI", "SO", "DUK", "CL", "ITW", "PNC", "AON",
        "MO", "BSX", "EOG", "SLB", "BDX", "HCA", "MCO", "ICE", "CME",
        "NOC", "LMT", "GD", "DE", "EMR", "FDX", "UPS", "NSC", "CSX",
        "WM", "ECL", "APD", "SHW", "NUE", "FCX", "DOW", "NEM", "COP",
        "OXY", "DVN", "HES", "PGR", "ALL", "TRV", "HIG", "MET", "PRU",
        "AFL", "HUM", "CVS", "MCK", "A", "BAX", "IDXX", "IQV", "LH",
        "DGX", "ALGN", "DXCM", "F", "GM", "AAL", "DAL", "UAL", "LUV",
        "CCL", "RCL", "MAR", "HLT", "SBUX", "YUM", "CMG", "NKE", "TGT",
        "AMZN", "EBAY", "ETSY", "DG", "DLTR", "KR"
    ],
    "Nasdaq100 Core": [
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "GOOGL", "GOOG",
        "AVGO", "COST", "NFLX", "TMUS", "AMD", "PEP", "CSCO", "ADBE",
        "TXN", "QCOM", "INTU", "AMAT", "MU", "LRCX", "KLAC", "SNPS",
        "CDNS", "MRVL", "WDAY", "CRWD", "PANW", "FTNT", "MNST", "ORLY",
        "CTAS", "PAYX", "FAST", "ROST", "ODFL", "VRSK", "ANSS", "DXCM",
        "IDXX", "ILMN", "REGN", "VRTX", "BIIB", "GILD", "AMGN", "ISRG",
        "ALGN", "MRNA", "ZM", "DOCU", "OKTA", "ZS", "DDOG", "SNOW",
        "MDB", "TEAM", "EBAY", "KHC", "MDLZ", "SBUX", "LULU", "ABNB",
        "BKNG", "EXPE", "INTC", "MCHP", "ADI", "NXPI", "ON", "MPWR",
        "ENPH", "FSLR", "PDD", "JD", "BIDU"
    ]
}

# Bottleneck watchlist — constrained inputs across sectors
BOTTLENECKS = {
    "AI Hardware": [
        "Rare HBM memory suppliers: MU, SAMSUNG (005930.KS)",
        "EUV lithography monopoly: ASML",
        "Advanced packaging: AMAT, LRCX",
        "Liquid cooling: VRT, MOD, NVT",
        "Power delivery/PDUs: ETN, ATKR"
    ],
    "Robotics": [
        "Harmonic/strain-wave reducers: HSYDF",
        "Rare-earth magnets: MP, LTHM",
        "Force/torque sensors: ATI (private), NOVT",
        "Precision bearings: (largely private/foreign)",
        "Robot vision/LIDAR: CGNX, KEYS"
    ],
    "Nuclear Energy": [
        "Enriched uranium supply: CCJ, LEU",
        "Zirconium cladding: (largely private)",
        "Specialized turbines: GEV",
        "SMR components: BWXT"
    ],
    "Drones": [
        "Solid-state batteries: (largely pre-commercial)",
        "LiDAR sensors: COHR",
        "RF/comms chips: QCOM, KEYS",
        "Counter-drone systems: KTOS, AVAV"
    ],
    "Fintech": [
        "Stablecoin infrastructure: CRCL, COIN",
        "Core banking rails: (largely private)",
        "Buy-now-pay-later rails: AFRM, UPST"
    ]
}

def get(endpoint, params={}):
    """Make a Finnhub API call with rate limit protection."""
    params["token"] = FINNHUB_KEY
    response = requests.get(f"{BASE_URL}{endpoint}", params=params)
    time.sleep(1.2)
    if response.status_code == 200:
        return response.json()
    return None

def get_quote(ticker):
    return get("/quote", {"symbol": ticker})

def get_candles(ticker, days=365):
    end = int(time.time())
    start = end - (days * 24 * 60 * 60)
    return get("/stock/candle", {
        "symbol": ticker,
        "resolution": "D",
        "from": start,
        "to": end
    })

def get_basic_financials(ticker):
    return get("/stock/metric", {"symbol": ticker, "metric": "all"})

def get_news(ticker):
    """Get recent news headlines for a ticker."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    week_ago = datetime.utcfromtimestamp(
        time.time() - 7 * 24 * 60 * 60
    ).strftime("%Y-%m-%d")
    data = get("/company-news", {
        "symbol": ticker,
        "from": week_ago,
        "to": today
    })
    if data and len(data) > 0:
        return [{"headline": n.get("headline"), "url": n.get("url"),
                 "datetime": n.get("datetime")} for n in data[:3]]
    return []

def compute_rsi(closes, period=14):
    """Compute RSI(14) from a list of closing prices."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0)) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def rsi_label(rsi):
    """Human readable RSI label."""
    if rsi is None:
        return "N/A"
    if rsi < 30:
        return "Extremely Oversold"
    if rsi <= 35:
        return "Oversold"
    if rsi >= 70:
        return "Overbought"
    return "Neutral"

def process_ticker(ticker, sector):
    """Build the full signal record for one ticker."""
    record = {
        "ticker": ticker,
        "sector": sector,
        "updated": datetime.utcnow().isoformat()
    }

    # Quote
    quote = get_quote(ticker)
    if not quote or quote.get("c", 0) == 0:
        return None
    record["price"] = quote.get("c")
    record["change_pct"] = round(quote.get("dp", 0), 2)
    record["prev_close"] = quote.get("pc")

    # Candles
    candles = get_candles(ticker)
    if candles and candles.get("s") == "ok":
        closes = candles["c"]
        volumes = candles["v"]

        record["low_52w"] = round(min(closes), 2)
        record["high_52w"] = round(max(closes), 2)
        record["pct_from_52w_low"] = round(
            (record["price"] - record["low_52w"]) / record["low_52w"] * 100, 2
        )
        record["pct_from_52w_high"] = round(
            (record["price"] - record["high_52w"]) / record["high_52w"] * 100, 2
        )

        rsi = compute_rsi(closes)
        record["rsi14"] = rsi
        record["rsi_label"] = rsi_label(rsi)

        if len(volumes) >= 30:
            avg_vol_30 = sum(volumes[-30:]) / 30
            record["volume_today"] = volumes[-1]
            record["volume_avg_30d"] = round(avg_vol_30, 0)
            record["volume_ratio"] = round(
                volumes[-1] / avg_vol_30, 2
            ) if avg_vol_30 > 0 else None

        if len(closes) >= 200:
            record["ma200"] = round(sum(closes[-200:]) / 200, 2)
        if len(closes) >= 50:
            record["ma50"] = round(sum(closes[-50:]) / 50, 2)

        # Biggest single-day drop in last 30 days
        recent = closes[-31:]
        worst_day = 0
        for i in range(1, len(recent)):
            pct = (recent[i] - recent[i-1]) / recent[i-1] * 100
            if pct < worst_day:
                worst_day = pct
        record["worst_day_30d"] = round(worst_day, 2)

        # Abrupt drop flag
        record["abrupt_drop_flag"] = record["worst_day_30d"] <= -8

    # Fundamentals
    fins = get_basic_financials(ticker)
    if fins and "metric" in fins:
        m = fins["metric"]
        record["market_cap"] = m.get("marketCapitalization")
        record["pe_ratio"] = m.get("peBasicExclExtraTTM")
        record["eps_ttm"] = m.get("epsTTM")

    # News (only fetch for flagged stocks to save API calls)
    needs_news = (
        record.get("rsi14") is not None and record["rsi14"] <= 35
    ) or record.get("abrupt_drop_flag")
    if needs_news:
        record["news"] = get_news(ticker)

    return record

def build_sector_summary(stocks):
    """
    For each sector compute:
    - avg RSI
    - % of stocks near 52w low (within 5%)
    - % of stocks near 52w high (within 5%)
    - momentum score (avg % from 52w low — higher = more momentum)
    - downtrodden score (% near 52w low — higher = more beaten down)
    """
    from collections import defaultdict
    sector_map = defaultdict(list)
    for s in stocks:
        sector_map[s["sector"]].append(s)

    summaries = []
    for sector, members in sector_map.items():
        valid = [m for m in members if m.get("rsi14") is not None]
        if not valid:
            continue
        near_low = [
            m for m in valid
            if m.get("pct_from_52w_low") is not None
            and m["pct_from_52w_low"] <= 5
        ]
        near_high = [
            m for m in valid
            if m.get("pct_from_52w_high") is not None
            and m["pct_from_52w_high"] >= -5
        ]
        avg_rsi = round(
            sum(m["rsi14"] for m in valid) / len(valid), 1
        )
        avg_from_low = round(
            sum(m.get("pct_from_52w_low", 0) for m in valid) / len(valid), 1
        )
        summaries.append({
            "sector": sector,
            "stock_count": len(valid),
            "avg_rsi": avg_rsi,
            "pct_near_52w_low": round(len(near_low) / len(valid) * 100, 1),
            "pct_near_52w_high": round(len(near_high) / len(valid) * 100, 1),
            "avg_pct_from_52w_low": avg_from_low,
            "downtrodden_score": round(len(near_low) / len(valid) * 100, 1),
            "momentum_score": avg_from_low,
            "bottlenecks": BOTTLENECKS.get(sector, [])
        })

    summaries.sort(key=lambda x: x["downtrodden_score"], reverse=True)
    return summaries

def main():
    print("Starting Non-Cents Market Filter data fetch...")

    # Build deduplicated universe, preserving first-seen sector tag
    seen = {}
    for sector, tickers in SECTORS.items():
        for t in tickers:
            if t not in seen:
                seen[t] = sector

    universe = list(seen.items())  # [(ticker, sector), ...]
    print(f"Universe: {len(universe)} unique tickers across "
          f"{len(SECTORS)} sectors")

    results = []
    errors = []

    for i, (ticker, sector) in enumerate(universe):
        print(f"[{i+1}/{len(universe)}] {ticker} ({sector})...")
        try:
            record = process_ticker(ticker, sector)
            if record:
                results.append(record)
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})
            print(f"  ERROR: {e}")

    # Build sector summaries
    sector_summaries = build_sector_summary(results)

    # Overreaction candidates
    overreaction = [
        r for r in results
        if r.get("change_pct", 0) <= -8
        and r.get("volume_ratio", 0) >= 2
        and r.get("rsi14", 100) <= 35
        and (r.get("market_cap") or 0) >= 2000  # $2B+
    ]

    # Near 52w low candidates
    near_lows = [
        r for r in results
        if r.get("pct_from_52w_low", 100) <= 5
    ]
    near_lows.sort(key=lambda x: x.get("pct_from_52w_low", 100))

    # Write cache
    os.makedirs("data", exist_ok=True)
    cache = {
        "generated": datetime.utcnow().isoformat(),
        "count": len(results),
        "stocks": results,
        "sector_summaries": sector_summaries,
        "overreaction_candidates": overreaction,
        "near_52w_lows": near_lows[:50],
        "errors": errors
    }
    with open("data/cache.json", "w") as f:
        json.dump(cache, f, indent=2)

    print(f"\n✓ {len(results)} stocks processed")
    print(f"✓ {len(sector_summaries)} sector summaries built")
    print(f"✓ {len(overreaction)} overreaction candidates flagged")
    print(f"✓ {len(near_lows)} stocks near 52w lows")
    print(f"✗ {len(errors)} errors")
    print("Cache written to data/cache.json")

if __name__ == "__main__":
    main()
