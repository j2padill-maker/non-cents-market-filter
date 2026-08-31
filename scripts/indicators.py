"""
Non-Cents — Briefing indicator engine.

Pure computation. Given an OHLCV pandas DataFrame (columns: Open, High, Low,
Close, Volume — as returned by yfinance with auto_adjust=True), compute the
default briefing indicator set plus price moves, and attach a plain-language
"read" to each so the narration layer (Phase 3) never has to interpret raw
numbers itself.

This is the single source of truth for indicator math. Both the briefing
builder and (later) the screener can import from here so the two never diverge.
No network, no I/O, no side effects.

Standard parameters (documented so the output is reproducible):
  RSI 14 (Wilder) · MACD 12/26/9 · Bollinger 20, 2σ · ATR 14 (Wilder) · MFI 14
  SMA 50 / 200 · 52-week window = 252 trading sessions · weekly move = 5 sessions
"""

import math
import pandas as pd
import numpy as np

# ── Default indicator set (what ships checked; user checkboxes drive this later)
DEFAULT_INDICATORS = [
    "rsi14",
    "macd",
    "bollinger_pctb",
    "pct_from_52w_low",
    "pct_from_52w_high",
    "price_vs_ma200",
    "atr14",
    "rel_volume",
    "mfi14",
]

WEEK_SESSIONS = 5
WINDOW_52W = 252


# ── low-level helpers ─────────────────────────────────────────────────────────

def _r(x, n=2):
    """Round, but pass through None / NaN / inf as None so JSON stays valid."""
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(xf) or math.isinf(xf):
        return None
    return round(xf, n)


def _wilder(series, period):
    """Wilder's smoothing via EWM (alpha = 1/period), matching the screener's RSI."""
    return series.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


# ── individual indicators ─────────────────────────────────────────────────────

def rsi(close, period=14):
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _wilder(gain, period)
    avg_loss = _wilder(loss, period)
    rs = avg_gain / avg_loss
    val = 100 - (100 / (1 + rs))
    v = _r(val.iloc[-1], 1)
    if v is None:
        return None
    return max(1.0, min(99.0, v))


def macd(close, fast=12, slow=26, signal=9):
    if len(close) < slow + signal:
        return None
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return {
        "macd": _r(macd_line.iloc[-1], 3),
        "signal": _r(signal_line.iloc[-1], 3),
        "hist": _r(hist.iloc[-1], 3),
        "hist_prev": _r(hist.iloc[-2], 3) if len(hist) > 1 else None,
    }


def bollinger(close, period=20, mult=2.0):
    if len(close) < period:
        return None
    mid = close.rolling(period).mean()
    sd = close.rolling(period).std(ddof=0)
    upper = mid + mult * sd
    lower = mid - mult * sd
    last_up, last_low = upper.iloc[-1], lower.iloc[-1]
    width = last_up - last_low
    pctb = (close.iloc[-1] - last_low) / width if width and width > 0 else None
    return {
        "upper": _r(last_up),
        "lower": _r(last_low),
        "mid": _r(mid.iloc[-1]),
        "pctb": _r(pctb, 3),
    }


def atr(high, low, close, period=14):
    if len(close) < period + 1:
        return None
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_series = _wilder(tr, period)
    val = atr_series.iloc[-1]
    last_price = close.iloc[-1]
    pct = (val / last_price * 100) if last_price else None
    return {"value": _r(val), "pct_of_price": _r(pct)}


def mfi(high, low, close, volume, period=14):
    if len(close) < period + 1:
        return None
    tp = (high + low + close) / 3
    raw_mf = tp * volume
    delta = tp.diff()
    pos_mf = raw_mf.where(delta > 0, 0.0)
    neg_mf = raw_mf.where(delta < 0, 0.0)
    pos_sum = pos_mf.rolling(period).sum()
    neg_sum = neg_mf.rolling(period).sum()
    mfr = pos_sum / neg_sum
    val = 100 - (100 / (1 + mfr))
    return _r(val.iloc[-1], 1)


def sma(close, period):
    if len(close) < period:
        return None
    return _r(close.rolling(period).mean().iloc[-1])


# ── plain-language interpretation ─────────────────────────────────────────────

def read_rsi(v):
    if v is None:
        return "N/A"
    if v < 30:
        return "Extremely oversold"
    if v < 40:
        return "Oversold"
    if v <= 60:
        return "Neutral"
    if v < 70:
        return "Firm — approaching overbought"
    return "Overbought"


def read_macd(m):
    if not m or m["macd"] is None or m["signal"] is None:
        return "N/A"
    above = m["macd"] > m["signal"]
    hist, prev = m.get("hist"), m.get("hist_prev")
    building = hist is not None and prev is not None and abs(hist) > abs(prev)
    if above:
        return "Bullish — MACD above signal" + (", momentum building" if building and hist > 0 else "")
    return "Bearish — MACD below signal" + (", momentum building to the downside" if building and hist < 0 else "")


def read_pctb(pctb):
    if pctb is None:
        return "N/A"
    if pctb > 1:
        return "Above the upper band — stretched to the upside"
    if pctb >= 0.8:
        return "Near the upper band"
    if pctb <= 0:
        return "Below the lower band — stretched to the downside"
    if pctb <= 0.2:
        return "Near the lower band"
    return "Mid-band — no extreme"


def read_pct_from_low(v):
    if v is None:
        return "N/A"
    if v <= 5:
        return "Sitting right at its 52-week low"
    if v <= 15:
        return "Just off its 52-week low"
    return f"{v:.0f}% above its 52-week low"


def read_pct_from_high(v):
    if v is None:
        return "N/A"
    if v >= -3:
        return "At or near its 52-week high"
    if v >= -15:
        return "Modestly below its 52-week high"
    return f"{abs(v):.0f}% below its 52-week high"


def read_vs_ma200(pct):
    if pct is None:
        return "N/A"
    if pct >= 0:
        return f"{pct:.0f}% above its 200-day average — long-term uptrend"
    return f"{abs(pct):.0f}% below its 200-day average — long-term downtrend"


def read_atr(pct):
    if pct is None:
        return "N/A"
    if pct >= 4:
        return "High daily volatility"
    if pct >= 2:
        return "Elevated volatility"
    return "Calm — low volatility"


def read_rel_volume(v):
    if v is None:
        return "N/A"
    if v >= 2:
        return "Heavy volume — well above average"
    if v >= 1.3:
        return "Above-average volume"
    if v <= 0.5:
        return "Light — quiet trading"
    return "Roughly average volume"


def read_mfi(v):
    if v is None:
        return "N/A"
    if v < 20:
        return "Oversold — money flowing out"
    if v > 80:
        return "Overbought — money flowing in"
    return "Neutral money flow"


# ── price moves ───────────────────────────────────────────────────────────────

def price_moves(df):
    close = df["Close"]
    last = close.iloc[-1]
    out = {
        "last": _r(last),
        "open": _r(df["Open"].iloc[-1]),
        "prev_close": _r(close.iloc[-2]) if len(close) > 1 else None,
    }
    # today's move: last close vs prior close
    if len(close) > 1 and close.iloc[-2]:
        out["move_day_pct"] = _r((last - close.iloc[-2]) / close.iloc[-2] * 100)
    # intraday open→close move
    op = df["Open"].iloc[-1]
    if op:
        out["move_open_close_pct"] = _r((last - op) / op * 100)
    # weekly move: last close vs close 5 sessions ago
    if len(close) > WEEK_SESSIONS and close.iloc[-1 - WEEK_SESSIONS]:
        base = close.iloc[-1 - WEEK_SESSIONS]
        out["move_week_pct"] = _r((last - base) / base * 100)
    return out


# ── orchestrator ──────────────────────────────────────────────────────────────

def compute_indicators(df, selected=None):
    """
    df: OHLCV DataFrame (Open/High/Low/Close/Volume), oldest → newest.
    selected: list of indicator keys to include (defaults to DEFAULT_INDICATORS).
    Returns (indicators_dict, extras_dict) where extras carries 52w hi/lo etc.
    """
    if selected is None:
        selected = DEFAULT_INDICATORS
    close, high, low, vol = df["Close"], df["High"], df["Low"], df["Volume"]
    last = close.iloc[-1]

    # 52-week window
    win = close.tail(WINDOW_52W)
    low_52w = _r(win.min())
    high_52w = _r(win.max())
    pct_low = _r((last - win.min()) / win.min() * 100) if win.min() else None
    pct_high = _r((last - win.max()) / win.max() * 100) if win.max() else None
    ma200 = sma(close, 200)
    ma50 = sma(close, 50)

    ind = {}

    if "rsi14" in selected:
        v = rsi(close)
        ind["rsi14"] = {"value": v, "read": read_rsi(v)}

    if "macd" in selected:
        m = macd(close)
        if m:
            m["read"] = read_macd(m)
        ind["macd"] = m

    if "bollinger_pctb" in selected:
        b = bollinger(close)
        if b:
            b["read"] = read_pctb(b.get("pctb"))
        ind["bollinger_pctb"] = b

    if "pct_from_52w_low" in selected:
        ind["pct_from_52w_low"] = {"value": pct_low, "read": read_pct_from_low(pct_low)}

    if "pct_from_52w_high" in selected:
        ind["pct_from_52w_high"] = {"value": pct_high, "read": read_pct_from_high(pct_high)}

    if "price_vs_ma200" in selected:
        pct = _r((last - ma200) / ma200 * 100) if ma200 else None
        ind["price_vs_ma200"] = {"ma200": ma200, "pct": pct, "read": read_vs_ma200(pct)}

    if "atr14" in selected:
        a = atr(high, low, close)
        if a:
            a["read"] = read_atr(a.get("pct_of_price"))
        ind["atr14"] = a

    if "rel_volume" in selected:
        rv = None
        if len(vol) >= 30:
            avg30 = vol.tail(30).mean()
            rv = _r(vol.iloc[-1] / avg30) if avg30 else None
        ind["rel_volume"] = {"value": rv, "read": read_rel_volume(rv)}

    if "mfi14" in selected:
        v = mfi(high, low, close, vol)
        ind["mfi14"] = {"value": v, "read": read_mfi(v)}

    extras = {
        "low_52w": low_52w,
        "high_52w": high_52w,
        "ma50": ma50,
        "ma200": ma200,
    }
    return ind, extras
