"""
סוכן 1: Screener Agent
- הפילטרים עצמם נמצאים ב-agents/filters.py (מקור אמת יחיד, בלי שרשרת elif).
- signal_date = תאריך הנר (bar_date), לא תאריך הריצה.
- נר חלקי / יום חג / נתונים מעוכבים: prepare_session מזהה ועוצר.
- mcap/float חסרים: fail-closed. כל טיקר נרשם (גם נדחה) ל-screener_all.csv.
"""
import time as _time_mod

import pandas as pd
import yfinance as yf

import config
from agents.filters import (  # noqa: F401  (re-export לתאימות)
    add_indicators,
    bar_date_of,
    compute_atr,
    compute_rsi,
    evaluate_filters,
    features_at,
)
from utils import expected_session_date

_sleep = _time_mod.sleep


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def get_benchmark():
    """(שינוי יומי, תאריך הנר) של SPY/QQQ. (None, None) אם אין נתונים."""
    try:
        df = yf.download(config.RS_BENCHMARK, period="10d", progress=False, auto_adjust=True)
    except Exception as e:
        print(f"  שגיאה בשליפת {config.RS_BENCHMARK}: {e}")
        return None, None
    if df is None or df.empty:
        return None, None
    df = _flatten(df).dropna(subset=["Close"])
    if len(df) < 2:
        return None, None
    last_close = float(df["Close"].iloc[-1])
    prev_close = float(df["Close"].iloc[-2])
    if prev_close <= 0:
        return None, None
    return (last_close - prev_close) / prev_close, bar_date_of(df.index[-1])


def prepare_session(enforce_session: bool = True) -> dict:
    """
    קובע אם יש נר חדש וסגור לסריקה.
    status: ok | benchmark_unavailable | no_new_bar (חג / נר חלקי / נתונים מעוכבים)
    """
    change, bar_date = get_benchmark()
    expected = expected_session_date()
    meta = {
        "benchmark_change": change,
        "session_date": bar_date,
        "expected_session_date": expected,
        "status": "ok",
    }
    if change is None:
        meta["status"] = "benchmark_unavailable"
    elif enforce_session and bar_date != expected:
        meta["status"] = "no_new_bar"
    return meta


def fetch_market_info(tk, retries: int = 2):
    """(market_cap, float_shares, error). עם retry/backoff - tk.info נכשל לעיתים ב-Actions."""
    err = None
    for attempt in range(retries + 1):
        try:
            info = tk.info or {}
            mc = info.get("marketCap")
            fl = info.get("floatShares")
            if mc is not None or fl is not None:
                return mc, fl, None
            err = "info_empty"
        except Exception as e:  # noqa: BLE001
            err = f"info:{e}"
        if attempt < retries:
            _sleep(1 + attempt)
    return None, None, err


def evaluate_ticker(ticker: str, benchmark_change: float, session_date=None) -> dict:
    """תמיד מחזיר רשומה (גם לטיקר שנדחה) - לשימוש screener_all.csv"""
    rec = {
        "ticker": ticker,
        "bar_date": None,
        "passed": False,
        "reject_reason": None,
        "all_failed": [],
        "fetch_error": None,
        "market_cap": None,
        "float_shares": None,
        "mcap_missing": None,
        "float_missing": None,
    }
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period="3mo")
    except Exception as e:  # noqa: BLE001
        rec.update(fetch_error=f"history:{e}", reject_reason="fetch_error", all_failed=["fetch_error"])
        return rec

    if df is None or df.empty:
        rec.update(fetch_error="no_history", reject_reason="fetch_error", all_failed=["fetch_error"])
        return rec
    df = _flatten(df).dropna(subset=["Close"])
    if len(df) < config.EMA_SLOW + 5:
        rec.update(fetch_error="insufficient_history", reject_reason="insufficient_history",
                   all_failed=["insufficient_history"])
        return rec

    bar_date = bar_date_of(df.index[-1])
    rec["bar_date"] = bar_date
    if session_date is not None and bar_date != session_date:
        rec.update(reject_reason="stale_bar", all_failed=["stale_bar"])
        return rec

    mc, fl, err = fetch_market_info(tk)
    rec.update(market_cap=mc, float_shares=fl, mcap_missing=mc is None, float_missing=fl is None)
    if err and mc is None and fl is None:
        rec["fetch_error"] = err

    df = add_indicators(df)
    f = features_at(df, len(df) - 1, benchmark_change)
    failed = evaluate_filters(f, mc, fl)

    rec.update(
        price=f["price"], rsi=f["rsi"], rvol=f["rvol"], atr_pct=f["atr_pct"],
        gap_pct=f["gap_pct"], relative_strength=f["relative_strength"],
        dollar_volume=f["dollar_volume"], benchmark_change=benchmark_change,
        all_failed=failed, reject_reason=failed[0] if failed else None, passed=not failed,
    )
    return rec


def to_candidate(rec: dict) -> dict:
    """רשומה שעברה -> מועמד לסוכנים הבאים (יחידות: אחוזים, כמו בלוג הישן)"""
    mc, fl = rec["market_cap"], rec["float_shares"]
    return {
        "ticker": rec["ticker"],
        "bar_date": rec["bar_date"],
        "price": round(rec["price"], 2),
        "rsi": round(rec["rsi"], 1),
        "rvol": round(rec["rvol"], 2),
        "atr_pct": round(rec["atr_pct"] * 100, 2),
        "dollar_volume_m": round(rec["dollar_volume"] / 1_000_000, 1),
        "market_cap_m": round(mc / 1_000_000, 1) if mc else None,
        "float_m": round(fl / 1_000_000, 1) if fl else None,
        "gap_pct": round(rec["gap_pct"] * 100, 2),
        "relative_strength_pct": round(rec["relative_strength"] * 100, 2),
        "benchmark_change_pct": round(rec["benchmark_change"] * 100, 2),
        "mcap_missing": int(bool(rec["mcap_missing"])),
        "float_missing": int(bool(rec["float_missing"])),
    }


def screen_ticker(ticker: str, benchmark_change: float, session_date=None):
    """מחזיר מועמד אם עבר את כל הפילטרים, אחרת None"""
    rec = evaluate_ticker(ticker, benchmark_change, session_date)
    return to_candidate(rec) if rec["passed"] else None


def run_screener_full(universe: list, benchmark_change: float, session_date=None):
    """(candidates, records, counts). records = כל הטיקרים, כולל נדחים."""
    records, candidates = [], []
    for ticker in universe:
        try:
            rec = evaluate_ticker(ticker, benchmark_change, session_date)
        except Exception as e:  # noqa: BLE001
            rec = {"ticker": ticker, "bar_date": None, "passed": False, "reject_reason": "fetch_error",
                   "all_failed": ["fetch_error"], "fetch_error": f"exception:{e}",
                   "market_cap": None, "float_shares": None, "mcap_missing": None, "float_missing": None}
        records.append(rec)
        if rec["passed"]:
            c = to_candidate(rec)
            candidates.append(c)
            print(f"  ✓ {ticker}: RSI={c['rsi']} RVOL={c['rvol']} RS={c['relative_strength_pct']}% "
                  f"$Vol={c['dollar_volume_m']}M")
        elif rec.get("fetch_error") and rec.get("reject_reason") in ("fetch_error", "insufficient_history"):
            print(f"  ✗ {ticker}: {rec['fetch_error']}")

    with_bar = [r for r in records if r.get("bar_date") is not None]
    mcap_missing = [r for r in with_bar if r.get("mcap_missing") or r.get("float_missing")]
    counts = {
        "scanned": len(records),
        "fetch_errors": sum(1 for r in records if r.get("reject_reason") in ("fetch_error", "insufficient_history")),
        "stale_bars": sum(1 for r in records if r.get("reject_reason") == "stale_bar"),
        "passed_technical": len(candidates),
        "mcap_missing_n": len(mcap_missing),
        "mcap_missing_pct": round(100.0 * len(mcap_missing) / len(with_bar), 1) if with_bar else 0.0,
    }
    return candidates, records, counts


def run_screener(universe: list) -> list:
    """תאימות לאחור: מחזיר רק את רשימת המועמדים (עם בדיקת סשן)."""
    meta = prepare_session(enforce_session=True)
    if meta["status"] != "ok":
        print(f"  סריקה נעצרה: {meta['status']}")
        return []
    candidates, _, _ = run_screener_full(universe, meta["benchmark_change"], meta["session_date"])
    return candidates
