import os
import json
import time
import requests
from datetime import datetime

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
BASE_URL = "https://finnhub.io/api/v1"

def get(endpoint, params={}):
    """Make a Finnhub API call with rate limit protection."""
    params["token"] = FINNHUB_KEY
    response = requests.get(f"{BASE_URL}{endpoint}", params=params)
    time.sleep(0.5)  # Stay well under 60 calls/min
    if response.status_code == 200:
        return response.json()
    return None

def get_sp500_tickers():
    """Pull S&P 500 constituents from Finnhub."""
    data = get("/index/constituents", {"symbol": "^GSPC"})
    if data and "constituents" in data:
        return set(data["constituents"])
    return set()

def get_nasdaq100_tickers():
    """Pull Nasdaq-100 constituents from Finnhub."""
    data = get("/index/constituents", {"symbol": "^NDX"})
    if data and "constituents" in data:
        return set(data["constituents"])
    return set()

def get_universe():
    """Combine and deduplicate S&P500 + Nasdaq-100."""
    sp500 = get_sp500_tickers()
    ndx100 = get_nasdaq100_tickers()
    universe = sorted(sp500.union(ndx100))
    print(f"Universe: {len(sp500)} S&P500 + {len(ndx100)} Nasdaq-100 = {len(universe)} unique tickers")
    return universe

def get_quote(ticker):
    """Get current quote for a ticker."""
    return get("/quote", {"symbol": ticker})

def get_candles(ticker, days=365):
    """Get daily candles for RSI, 52wk low, moving averages."""
    end = int(time.time())
    start = end - (days * 24 * 60 * 60)
    return get("/stock/candle", {
        "symbol": ticker,
        "resolution": "D",
        "from": start,
        "to": end
    })

def get_basic_financials(ticker):
    """Get fundamentals: market cap, net income."""
    return get("/stock/metric", {"symbol": ticker, "metric": "all"})

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

def process_ticker(ticker):
    """Build the full signal record for one ticker."""
    record = {"ticker": ticker, "updated": datetime.utcnow().isoformat()}

    # Quote
    quote = get_quote(ticker)
    if not quote or quote.get("c", 0) == 0:
        return None
    record["price"] = quote.get("c")
    record["change_pct"] = round(quote.get("dp", 0), 2)
    record["prev_close"] = quote.get("pc")

    # Candles (1 year of daily data)
    candles = get_candles(ticker)
    if candles and candles.get("s") == "ok":
        closes = candles["c"]
        highs = candles["h"]
        volumes = candles["v"]

        # 52-week low & high
        record["low_52w"] = round(min(closes), 2)
        record["high_52w"] = round(max(closes), 2)
        record["pct_from_52w_low"] = round(
            (record["price"] - record["low_52w"]) / record["low_52w"] * 100, 2
        )

        # RSI(14)
        record["rsi14"] = compute_rsi(closes)

        # Volume: today vs 30-day average
        if len(volumes) >= 30:
            avg_vol_30 = sum(volumes[-30:]) / 30
            record["volume_today"] = volumes[-1]
            record["volume_avg_30d"] = round(avg_vol_30, 0)
            record["volume_ratio"] = round(volumes[-1] / avg_vol_30, 2) if avg_vol_30 > 0 else None

        # 200-day moving average
        if len(closes) >= 200:
            record["ma200"] = round(sum(closes[-200:]) / 200, 2)
        
        # Biggest single-day drop in last 30 days
        recent_closes = closes[-31:]
        worst_day = 0
        for i in range(1, len(recent_closes)):
            pct = (recent_closes[i] - recent_closes[i-1]) / recent_closes[i-1] * 100
            if pct < worst_day:
                worst_day = pct
        record["worst_day_30d"] = round(worst_day, 2)

    # Fundamentals
    fins = get_basic_financials(ticker)
    if fins and "metric" in fins:
        m = fins["metric"]
        record["market_cap"] = m.get("marketCapitalization")  # in millions
        record["pe_ratio"] = m.get("peBasicExclExtraTTM")
        record["eps_ttm"] = m.get("epsTTM")

    return record

def main():
    print("Starting Non-Cents Market Filter data fetch...")
    universe = get_universe()
    
    results = []
    errors = []
    
    for i, ticker in enumerate(universe):
        print(f"[{i+1}/{len(universe)}] Processing {ticker}...")
        try:
            record = process_ticker(ticker)
            if record:
                results.append(record)
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})
            print(f"  ERROR on {ticker}: {e}")

    # Write cache
    os.makedirs("data", exist_ok=True)
    cache = {
        "generated": datetime.utcnow().isoformat(),
        "count": len(results),
        "stocks": results,
        "errors": errors
    }
    with open("data/cache.json", "w") as f:
        json.dump(cache, f, indent=2)

    print(f"\nDone. {len(results)} stocks cached, {len(errors)} errors.")
    print("Cache written to data/cache.json")

if __name__ == "__main__":
    main()
