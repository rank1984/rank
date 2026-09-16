import os
import time
import requests
from datetime import datetime, timedelta
from typing import Optional

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "")
SEC_BASE = "https://data.sec.gov"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

HIGH_RISK_FORMS = {"S-1", "S-1/A", "424B3", "424B5", "EFFECT"}
MEDIUM_RISK_FORMS = {"S-3", "S-3/A"}
WATCH_FORMS = {"8-K", "10-Q", "10-K"}

ATM_KEYWORDS = (
    "at-the-market", "at the market offering",
    "sales agreement", "prospectus supplement",
    "shelf registration",
)

# SEC: max ~10 requests/sec. אנחנו שמרנים יותר.
_MIN_INTERVAL = 0.15


class SECFilingFilter:
    def __init__(self, cache_ttl_hours: int = 24, lookback_days: int = 90):
        if not SEC_USER_AGENT:
            raise RuntimeError(
                "SEC_USER_AGENT env var is required (format: 'name email'). "
                "SEC blocks requests without a valid User-Agent."
            )
        self._lookback_days = lookback_days
        self._cache: dict = {}
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._last_request_ts = 0.0
        self._ticker_to_cik: dict[str, str] = {}
        self._load_ticker_map()

    # ---------- HTTP ----------
    def _headers(self):
        return {"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_request_ts = time.monotonic()

    def _get(self, url: str, retries: int = 3, json=True):
        for attempt in range(retries):
            self._throttle()
            try:
                r = requests.get(url, headers=self._headers(), timeout=10)
                if r.status_code in (429, 503):
                    time.sleep(1.5 ** attempt)
                    continue
                r.raise_for_status()
                return r.json() if json else r.text
            except requests.RequestException as e:
                if attempt == retries - 1:
                    print(f"[SEC] GET failed {url}: {e}")
                    return None
                time.sleep(1.5 ** attempt)
        return None

    # ---------- CIK ----------
    def _load_ticker_map(self):
        data = self._get(SEC_TICKERS_URL)
        if not data:
            print("[SEC] ticker map unavailable — filter will block all trades.")
            return
        self._ticker_to_cik = {
            v["ticker"].upper(): str(v["cik_str"]).zfill(10)
            for v in data.values()
        }

    def _get_cik(self, symbol: str) -> Optional[str]:
        return self._ticker_to_cik.get(symbol.upper())

    # ---------- Filings ----------
    def _get_filings(self, cik: str) -> Optional[dict]:
        key = f"filings_{cik}"
        cached = self._cache.get(key)
        if cached and datetime.utcnow() - cached["ts"] < self._cache_ttl:
            return cached["data"]
        data = self._get(f"{SEC_BASE}/submissions/CIK{cik}.json")
        if data:
            self._cache[key] = {"ts": datetime.utcnow(), "data": data}
        return data

    def _scan_for_atm(self, cik: str, accession: str, primary_doc: str) -> bool:
        """סורק 8-K/10-Q אחר מילות מפתח של ATM. cache ב-24h."""
        key = f"atm_{accession}"
        cached = self._cache.get(key)
        if cached and datetime.utcnow() - cached["ts"] < self._cache_ttl:
            return cached["data"]

        url = f"{SEC_ARCHIVES}/{int(cik)}/{accession.replace('-', '')}/{primary_doc}"
        text = self._get(url, json=False)
        found = False
        if text:
            low = text.lower()
            found = any(kw in low for kw in ATM_KEYWORDS)
        self._cache[key] = {"ts": datetime.utcnow(), "data": found}
        return found

    # ---------- Public API ----------
    def check(self, symbol: str) -> dict:
        """
        מחזיר dict עם רמת סיכון דילול, allowed, ו-size multiplier.
        unknown => חסום. אין ברירת מחדל מתירנית.
        """
        base = {
            "symbol": symbol,
            "source": "SEC EDGAR",
            "fetched_at": datetime.utcnow().isoformat(),
        }
        cik = self._get_cik(symbol)
        if not cik:
            return {**base, "dilution_risk": "unknown",
                    "trade_allowed": False, "position_size_multiplier": 0.0,
                    "reason": "CIK not found"}

        data = self._get_filings(cik)
        if not data:
            return {**base, "cik": cik, "dilution_risk": "unknown",
                    "trade_allowed": False, "position_size_multiplier": 0.0,
                    "reason": "Filings unavailable"}

        cutoff = datetime.utcnow() - timedelta(days=self._lookback_days)
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        active, atm_detected = [], False
        for form, d, acc, pdoc in zip(forms, dates, accessions, primary_docs):
            try:
                fd = datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                continue
            if fd < cutoff:
                continue
            if form in HIGH_RISK_FORMS or form in MEDIUM_RISK_FORMS:
                active.append({"form": form, "date": d, "accession": acc})
            elif form in WATCH_FORMS:
                active.append({"form": form, "date": d, "accession": acc})
                if not atm_detected and pdoc:
                    if self._scan_for_atm(cik, acc, pdoc):
                        atm_detected = True

        has_high = any(f["form"] in HIGH_RISK_FORMS for f in active)
        has_medium = any(f["form"] in MEDIUM_RISK_FORMS for f in active)

        if has_high or atm_detected:
            risk, allowed, mult = "high", False, 0.0
        elif has_medium:
            risk, allowed, mult = "medium", True, 0.5
        else:
            risk, allowed, mult = "low", True, 1.0

        return {
            **base,
            "cik": cik,
            "dilution_risk": risk,
            "active_forms": sorted({f["form"] for f in active}),
            "filings": active,
            "atm_detected": atm_detected,
            "trade_allowed": allowed,
            "position_size_multiplier": mult,
            "reason": "Active dilution risk" if risk == "high" else "OK",
        }
