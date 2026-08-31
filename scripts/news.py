"""
Non-Cents — News + SEC filings for briefings (Phase 2).

Per ticker, assembles:
  · recent company-news headlines from Finnhub (needs FINNHUB_API_KEY, the same
    key the screener already uses) — headline, source, link, time, short summary.
  · recent SEC EDGAR filings (free, no key) — 8-K / 10-Q / 10-K / 6-K with a link,
    so the briefing can flag "they just reported" on filing days.

We store headline + source + link + a short summary only — never full articles
(correct for the data license, and for going public later). Everything degrades
gracefully: no key → no Finnhub news; any network/parse failure → empty list,
never a crash. No global side effects beyond an in-process CIK-map cache.
"""

import os
import requests
from datetime import datetime, timedelta

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
FINNHUB_BASE = "https://finnhub.io/api/v1"
# SEC requires a User-Agent in "Name email" form, or it returns 403. Override
# with the SEC_USER_AGENT env var if you want a different contact.
SEC_UA = os.environ.get("SEC_USER_AGENT", "Non-Cents Market Filter admin@noncentsmarket.com")
SEC_HEADERS = {"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate", "Accept": "application/json"}

_cik_map = None  # ticker -> zero-padded CIK, fetched once per process


def _get_json(url, headers=None, params=None, timeout=12):
    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        print(f"  news: {url} -> HTTP {r.status_code}")
    except Exception as e:
        print(f"  news: fetch error {url}: {e}")
    return None


# ── Finnhub company news ──────────────────────────────────────────────────────

def get_finnhub_news(ticker, days=7, cap=6):
    if not FINNHUB_KEY:
        return []
    today = datetime.utcnow().date()
    frm = today - timedelta(days=days)
    data = _get_json(f"{FINNHUB_BASE}/company-news", params={
        "symbol": ticker, "from": frm.isoformat(), "to": today.isoformat(),
        "token": FINNHUB_KEY,
    })
    if not isinstance(data, list):
        return []
    items, seen = [], set()
    for a in data:
        h = (a.get("headline") or "").strip()
        key = h.lower()
        if not h or key in seen:
            continue
        seen.add(key)
        items.append({
            "headline": h,
            "source": (a.get("source") or "").strip(),
            "url": a.get("url") or "",
            "datetime": a.get("datetime"),          # epoch seconds
            "summary": (a.get("summary") or "").strip()[:400],
        })
    items.sort(key=lambda x: x.get("datetime") or 0, reverse=True)
    return items[:cap]


# ── SEC EDGAR filings ─────────────────────────────────────────────────────────

def _cik_for(ticker):
    global _cik_map
    if _cik_map is None:
        _cik_map = {}
        data = _get_json("https://www.sec.gov/files/company_tickers.json",
                         headers=SEC_HEADERS)
        if isinstance(data, dict):
            for row in data.values():
                t = (row.get("ticker") or "").upper()
                if t:
                    _cik_map[t] = str(row.get("cik_str")).zfill(10)
    return _cik_map.get(ticker.upper())


_FORM_TITLES = {
    "8-K": "Material event (8-K)",
    "10-Q": "Quarterly report (10-Q)",
    "10-K": "Annual report (10-K)",
    "6-K": "Foreign issuer report (6-K)",
    "20-F": "Foreign annual report (20-F)",
}


def get_sec_filings(ticker, cap=3, forms=("8-K", "10-Q", "10-K", "6-K", "20-F")):
    cik = _cik_for(ticker)
    if not cik:
        return []
    data = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json",
                     headers=SEC_HEADERS)
    if not data:
        return []
    recent = (data.get("filings") or {}).get("recent") or {}
    forms_list = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accns = recent.get("accessionNumber") or []
    prim = recent.get("primaryDocument") or []
    out = []
    for i, form in enumerate(forms_list):
        if form not in forms:
            continue
        accn = accns[i].replace("-", "") if i < len(accns) else ""
        doc = prim[i] if i < len(prim) else ""
        if accn and doc:
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{doc}"
        else:
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form}"
        out.append({
            "form": form,
            "title": _FORM_TITLES.get(form, form),
            "date": dates[i] if i < len(dates) else "",
            "url": url,
        })
        if len(out) >= cap:
            break
    return out


# ── orchestrator ──────────────────────────────────────────────────────────────

def assemble(ticker):
    """Return {'news': [...], 'filings': [...]} for a ticker; never raises."""
    try:
        news = get_finnhub_news(ticker)
    except Exception as e:
        print(f"  news: Finnhub failed for {ticker}: {e}")
        news = []
    try:
        filings = get_sec_filings(ticker)
    except Exception as e:
        print(f"  news: SEC failed for {ticker}: {e}")
        filings = []
    return {"news": news, "filings": filings}
