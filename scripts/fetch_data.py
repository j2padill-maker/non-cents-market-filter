import os
import json
import time
import requests
from datetime import datetime, timedelta

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
BASE_URL = "https://finnhub.io/api/v1"

# ── UNIVERSE ──────────────────────────────────────────────────────────────────

SECTORS = {
    "AI Hardware": [
        "NVDA", "AMD", "INTC", "MU", "AMAT", "LRCX", "AVGO", "ASML", "TSM",
        "DELL", "SMCI", "VRT", "ETN", "ATKR", "MOD", "NVT", "FORM", "COHR", "ATSK"
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
        "BLDR", "BLD", "TREX", "OC", "MAS", "CARR", "TT", "LII", "SHW", "LOW", "HD"
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

SECTOR_KEYWORDS = {
    "AI Hardware": ["nvidia", "semiconductor", "chip", "gpu", "tsmc", "asml"],
    "AI Software": ["artificial intelligence", "ai software", "cloud", "cybersecurity"],
    "Robotics": ["robotics", "automation", "robot", "autonomous", "humanoid"],
    "Homebuilders": ["homebuilder", "housing", "mortgage", "home sales", "construction"],
    "Fintech": ["fintech", "payments", "crypto", "banking", "stablecoin"],
    "Nuclear Energy": ["nuclear", "uranium", "energy", "smr", "reactor"],
    "Drones": ["drone", "uav", "unmanned", "aerospace", "defense"],
    "Mining & Materials": ["mining", "copper", "gold", "lithium", "metals"],
    "Energy": ["oil", "gas", "energy", "petroleum", "opec"],
    "S&P500 Core": ["market", "s&p", "fed", "economy", "earnings"],
    "Nasdaq100 Core": ["nasdaq", "tech", "technology", "growth stocks"]
}

BOTTLENECKS = {
    "AI Hardware": [
        "HBM memory suppliers: MU, Samsung",
        "EUV lithography monopoly: ASML",
        "Advanced packaging: AMAT, LRCX",
        "Liquid cooling: VRT, MOD, NVT",
        "Power delivery/PDUs: ETN, ATKR"
    ],
    "Robotics": [
        "Harmonic/strain-wave reducers: HSYDF",
        "Rare-earth magnets: MP, LTHM",
        "Force/torque sensors: NOVT",
        "Robot vision/LIDAR: CGNX, KEYS"
    ],
    "Nuclear Energy": [
        "Enriched uranium supply: CCJ, LEU",
        "Specialized turbines: GEV",
        "SMR components: BWXT"
    ],
    "Drones": [
        "LiDAR sensors: COHR",
        "RF/comms chips: QCOM, KEYS",
        "Counter-drone systems: KTOS, AVAV"
    ],
    "Fintech": [
        "Stablecoin infrastructure: CRCL, COIN",
        "Buy-now-pay-later rails: AFRM, UPST"
    ],
    "Mining & Materials": [
        "Rare-earth processing: MP",
        "Lithium supply: ALB, LTHM",
        "Copper smelting capacity: FCX"
    ]
}

# ── FINNHUB API ───────────────────────────────────────────────────────────────

def finnhub_get(endpoint, params={}, retries=2):
    p = dict(params)
    p["token"] = FINNHUB_KEY
    for attempt in range(retries):
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params=p, timeout=10)
            time.sleep(0.8)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                print("  Rate limited, waiting 15s...")
                time.sleep(15)
            else:
                return None
        except Exception as e:
            print(f"  Request error: {e}")
            time.sleep(2)
    return None

def get_quote(ticker):
    return finnhub_get("/quote", {"symbol": ticker})

def get_basic_financials(ticker):
    return finnhub_get("/stock/metric", {"symbol": ticker, "metric": "all"})

def get_company_profile(ticker):
    """Get company name, description, industry, website, logo."""
    return finnhub_get("/stock/profile2", {"symbol": ticker})

def get_stock_news(ticker):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    data = finnhub_get("/company-news", {"symbol": ticker, "from": week_ago, "to": today})
    if data and len(data) > 0:
        return [{"headline": n.get("headline"), "url": n.get("url"),
                 "datetime": n.get("datetime"), "source": n.get("source", "")}
                for n in data[:5]]
    return []

def get_sector_news(sector):
    keywords = SECTOR_KEYWORDS.get(sector, [])
    if not keywords:
        return []
    data = finnhub_get("/news", {"category": "general"})
    if not data:
        return []
    relevant = []
    for item in data:
        headline = (item.get("headline") or "").lower()
        summary = (item.get("summary") or "").lower()
        text = headline + " " + summary
        if any(kw.lower() in text for kw in keywords):
            relevant.append({
                "headline": item.get("headline"),
                "url": item.get("url"),
                "datetime": item.get("datetime"),
                "source": item.get("source", ""),
                "summary": (item.get("summary") or "")[:200]
            })
        if len(relevant) >= 8:
            break
    return relevant

# ── YFINANCE FOR CANDLES / RSI ────────────────────────────────────────────────

def get_yfinance_data(ticker):
    """Use yfinance to get price history for RSI, 52w high/low, MA calculations."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        # Get 1 year of daily data
        hist = stock.history(period="2y", auto_adjust=False)
        if hist.empty:
            return None
        closes = hist["Close"].tolist()
        volumes = hist["Volume"].tolist()
        return {"closes": closes, "volumes": volumes}
    except Exception as e:
        print(f"  yfinance error for {ticker}: {e}")
        return None

def compute_rsi(closes, period=14):
    """
    Compute true RSI(14) using pandas ewm with Wilder's smoothing.
    This matches the industry standard used by TradingView, Finviz etc.
    Requires at least 100 periods for values to stabilize properly.
    """
    if not closes or len(closes) < period + 1:
        return None
    try:
        import pandas as pd
        import numpy as np

        s = pd.Series(closes)
        delta = s.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        # Wilder's smoothing: alpha = 1/period, adjust=False
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # Get the last value
        result = round(float(rsi.iloc[-1]), 1)

        # Clamp to valid range
        return max(1.0, min(99.0, result))
    except Exception as e:
        print(f"  RSI calculation error: {e}")
        return None

def rsi_label(rsi):
    if rsi is None: return "N/A"
    if rsi < 30: return "Extremely Oversold"
    if rsi <= 35: return "Oversold"
    if rsi >= 70: return "Overbought"
    return "Neutral"

# ── PROCESS ONE TICKER ────────────────────────────────────────────────────────

def process_ticker(ticker, sector):
    record = {
        "ticker": ticker,
        "sector": sector,
        "updated": datetime.utcnow().isoformat()
    }

    # Real-time quote from Finnhub
    quote = get_quote(ticker)
    if not quote or quote.get("c", 0) == 0:
        return None
    record["price"] = quote.get("c")
    record["change_pct"] = round(quote.get("dp", 0), 2)
    record["prev_close"] = quote.get("pc")

    # Company profile from Finnhub
    profile = get_company_profile(ticker)
    if profile:
        record["company_name"] = profile.get("name", "")
        record["description"] = profile.get("description", "")
        record["industry"] = profile.get("finnhubIndustry", "")
        record["website"] = profile.get("weburl", "")
        record["logo"] = profile.get("logo", "")
        record["country"] = profile.get("country", "")
        record["exchange"] = profile.get("exchange", "")

    # yfinance: candles for RSI, 52w, volume, MAs
    yf_data = get_yfinance_data(ticker)
    if yf_data:
        closes = yf_data["closes"]
        volumes = yf_data["volumes"]

        # 52-week high and low from actual price history
        record["low_52w"] = round(min(closes), 2)
        record["high_52w"] = round(max(closes), 2)

        if record["price"] and record["low_52w"] and record["high_52w"]:
            record["pct_from_52w_low"] = round(
                (record["price"] - record["low_52w"]) / record["low_52w"] * 100, 2
            )
            record["pct_from_52w_high"] = round(
                (record["price"] - record["high_52w"]) / record["high_52w"] * 100, 2
            )

        # True RSI(14) using Wilder's method
        rsi = compute_rsi(closes)
        record["rsi14"] = rsi
        record["rsi_label"] = rsi_label(rsi)

        # Volume ratio
        if len(volumes) >= 30:
            avg_vol_30 = sum(volumes[-30:]) / 30
            record["volume_today"] = volumes[-1]
            record["volume_avg_30d"] = round(avg_vol_30, 0)
            record["volume_ratio"] = round(
                volumes[-1] / avg_vol_30, 2
            ) if avg_vol_30 > 0 else None

        # Moving averages
        if len(closes) >= 200:
            record["ma200"] = round(sum(closes[-200:]) / 200, 2)
        if len(closes) >= 50:
            record["ma50"] = round(sum(closes[-50:]) / 50, 2)

        # Worst single day drop in last 30 days
        recent = closes[-31:]
        worst_day = 0
        for i in range(1, len(recent)):
            pct = (recent[i] - recent[i-1]) / recent[i-1] * 100
            if pct < worst_day:
                worst_day = pct
        record["worst_day_30d"] = round(worst_day, 2)
        record["abrupt_drop_flag"] = worst_day <= -8

    else:
        # Fallback to Finnhub metrics for 52W if yfinance fails
        fins = get_basic_financials(ticker)
        if fins and "metric" in fins:
            m = fins["metric"]
            high_52w = m.get("52WeekHigh")
            low_52w = m.get("52WeekLow")
            # Sanity check - reject if values are wildly different from current price
            if high_52w and low_52w and record.get("price"):
                price = record["price"]
                if low_52w > price * 0.1 and high_52w < price * 10:
                    record["high_52w"] = high_52w
                    record["low_52w"] = low_52w
                    record["pct_from_52w_low"] = round(
                        (price - low_52w) / low_52w * 100, 2
                    )
                    record["pct_from_52w_high"] = round(
                        (price - high_52w) / high_52w * 100, 2
                    )

    # Fundamentals from Finnhub
    fins = get_basic_financials(ticker)
    if fins and "metric" in fins:
        m = fins["metric"]
        record["market_cap"] = m.get("marketCapitalization")
        record["pe_ratio"] = m.get("peBasicExclExtraTTM")
        record["eps_ttm"] = m.get("epsTTM")
        record["beta"] = m.get("beta")
        record["dividend_yield"] = m.get("currentDividendYieldTTM")
        record["revenue_growth"] = m.get("revenueGrowthTTMYoy")

    # News for flagged stocks
    needs_news = (
        record.get("rsi14") is not None and record["rsi14"] <= 35
    ) or record.get("abrupt_drop_flag")
    if needs_news:
        record["news"] = get_stock_news(ticker)

    return record

# ── SECTOR SUMMARIES ──────────────────────────────────────────────────────────

def build_sector_summaries(stocks):
    from collections import defaultdict
    sector_map = defaultdict(list)
    for s in stocks:
        sector_map[s["sector"]].append(s)

    summaries = []
    for sector, members in sector_map.items():
        with_rsi = [m for m in members if m.get("rsi14") is not None]
        with_low = [m for m in members if m.get("pct_from_52w_low") is not None]
        near_low = [m for m in with_low if m["pct_from_52w_low"] <= 5]

        avg_rsi = round(
            sum(m["rsi14"] for m in with_rsi) / len(with_rsi), 1
        ) if with_rsi else None
        avg_from_low = round(
            sum(m["pct_from_52w_low"] for m in with_low) / len(with_low), 1
        ) if with_low else None
        near_low_pct = round(
            len(near_low) / len(with_low) * 100, 1
        ) if with_low else 0

        print(f"  Fetching news for: {sector}")
        sector_news = get_sector_news(sector)

        summaries.append({
            "sector": sector,
            "stock_count": len(members),
            "avg_rsi": avg_rsi,
            "pct_near_52w_low": near_low_pct,
            "avg_pct_from_52w_low": avg_from_low,
            "downtrodden_score": near_low_pct,
            "momentum_score": avg_from_low or 0,
            "bottlenecks": BOTTLENECKS.get(sector, []),
            "news": sector_news,
            "news_count": len(sector_news)
        })

    summaries.sort(key=lambda x: x["downtrodden_score"], reverse=True)
    return summaries

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    try:
        import yfinance as yf
        print("✓ yfinance available")
    except ImportError:
        print("✗ yfinance not installed — run: pip install yfinance")
        return

    print("Starting Non-Cents Market Filter data fetch...")
    print("Finnhub: quotes + company profiles + news + fundamentals")
    print("yfinance: candles + true RSI(14) + 52W high/low + volume")

    seen = {}
    for sector, tickers in SECTORS.items():
        for t in tickers:
            if t not in seen:
                seen[t] = sector

    universe = list(seen.items())
    print(f"\nUniverse: {len(universe)} unique tickers across {len(SECTORS)} sectors\n")

    results = []
    errors = []

    for i, (ticker, sector) in enumerate(universe):
        print(f"[{i+1}/{len(universe)}] {ticker} ({sector})...")
        try:
            record = process_ticker(ticker, sector)
            if record:
                results.append(record)
                rsi_str = f"RSI:{record['rsi14']}" if record.get('rsi14') else "RSI:—"
                low_str = f"52wL:${record['low_52w']}" if record.get('low_52w') else "52wL:—"
                high_str = f"52wH:${record['high_52w']}" if record.get('high_52w') else "52wH:—"
                desc_str = "✓ desc" if record.get('description') else "✗ no desc"
                print(f"  ✓ ${record['price']} {rsi_str} {low_str} {high_str} {desc_str}")
            else:
                print(f"  ✗ No data returned")
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})
            print(f"  ✗ ERROR: {e}")

    print(f"\nBuilding sector summaries and fetching news...")
    sector_summaries = build_sector_summaries(results)

    overreaction = [
        r for r in results
        if r.get("change_pct", 0) <= -8
        and r.get("volume_ratio", 0) >= 2
        and (r.get("rsi14", 100) or 100) <= 35
        and (r.get("market_cap") or 0) >= 2000
    ]

    near_lows = sorted(
        [r for r in results if r.get("pct_from_52w_low", 100) <= 5],
        key=lambda x: x.get("pct_from_52w_low", 100)
    )

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

    rsi_count = sum(1 for r in results if r.get("rsi14") is not None)
    low_count = sum(1 for r in results if r.get("low_52w") is not None)
    desc_count = sum(1 for r in results if r.get("description"))

    print(f"\n✓ {len(results)} stocks processed")
    print(f"✓ {rsi_count}/{len(results)} stocks have RSI data")
    print(f"✓ {low_count}/{len(results)} stocks have 52W data")
    print(f"✓ {desc_count}/{len(results)} stocks have company descriptions")
    print(f"✓ {len(sector_summaries)} sector summaries with news")
    print(f"✓ {len(overreaction)} overreaction candidates")
    print(f"✓ {len(near_lows)} stocks near 52W lows")
    print(f"✗ {len(errors)} errors")
    print("Cache written to data/cache.json")

if __name__ == "__main__":
    main()
