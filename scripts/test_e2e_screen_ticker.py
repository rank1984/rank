"""
מבחן קצה-לקצה: yfinance מוחלף ב-stub, והנתיב החי (screen_ticker / run_screener_full) רץ באמת.
הרצה: python scripts/test_e2e_screen_ticker.py
"""
import _stubs
from datetime import date

import _synthetic as S

STRONG, WEAK = S.make_strong(), S.make_weak()
OK_INFO = {"marketCap": 300e6, "floatShares": 50e6}
REG = {
    "STRONG": {"df": STRONG, "info": OK_INFO},
    "WEAK": {"df": WEAK, "info": OK_INFO},
    "NOMCAP": {"df": STRONG, "info": {}},
    "INFOERR": {"df": STRONG, "info": RuntimeError("429")},
    "BIGCAP": {"df": STRONG, "info": {"marketCap": 5e9, "floatShares": 50e6}},
}
_stubs.install(REG, S.spy_frame(S.END, 0.0))
_stubs.no_sleep()

import agents.screener_agent as sa  # noqa: E402

BAR = date(2026, 9, 28)

# 1. חלש -> None (הנתיב החי באמת קורא ל-evaluate_filters)
assert sa.screen_ticker("WEAK", 0.0, BAR) is None
rec = sa.evaluate_ticker("WEAK", 0.0, BAR)
assert not rec["passed"]
for must in ("no_ema_breakout", "rsi_out_of_range", "rvol_too_low"):
    assert must in rec["all_failed"], rec["all_failed"]
print("OK weak -> None | all_failed =", ",".join(rec["all_failed"]))

# 2. חזק -> מועמד, תאריך מהנר, יחידות באחוזים
c = sa.screen_ticker("STRONG", 0.0, BAR)
assert c is not None, "strong לא עבר"
assert c["bar_date"] == BAR
assert 5 <= c["gap_pct"] <= 25 and 55 <= c["rsi"] <= 70 and c["rvol"] >= 3
assert c["market_cap_m"] == 300.0 and c["float_m"] == 50.0
print("OK strong -> candidate", {k: c[k] for k in ("ticker", "bar_date", "price", "rsi", "rvol", "gap_pct")})

# 3. mcap/float חסרים או tk.info נכשל -> fail-closed
for t in ("NOMCAP", "INFOERR"):
    rec = sa.evaluate_ticker(t, 0.0, BAR)
    assert not rec["passed"] and rec["all_failed"] == ["missing_mcap_or_float"], (t, rec["all_failed"])
    assert rec["mcap_missing"] is True
print("OK missing mcap/float -> fail-closed")

# 4. mcap מחוץ לטווח
rec = sa.evaluate_ticker("BIGCAP", 0.0, BAR)
assert rec["all_failed"] == ["market_cap_out_of_range"], rec["all_failed"]
print("OK market_cap_out_of_range")

# 5. נר ישן
rec = sa.evaluate_ticker("STRONG", 0.0, date(2026, 9, 25))
assert rec["reject_reason"] == "stale_bar" and not rec["passed"]
print("OK stale bar rejected")

# 6. run_screener_full: כל הטיקרים נרשמים, כולל שנכשלו בשליפה
cands, recs, counts = sa.run_screener_full(["STRONG", "WEAK", "NOMCAP", "MISSING_FROM_REGISTRY"], 0.0, BAR)
assert [c["ticker"] for c in cands] == ["STRONG"]
assert len(recs) == 4 and counts["scanned"] == 4
assert counts["fetch_errors"] == 1, counts
assert counts["mcap_missing_n"] == 1, counts
print("OK run_screener_full counts:", counts)

# 7. prepare_session: SPY חסר -> benchmark_unavailable; נר שונה מהצפוי -> no_new_bar
import pandas as pd  # noqa: E402
sys_mod = __import__("sys").modules["yfinance"]
sys_mod.download = lambda *a, **k: pd.DataFrame()
assert sa.prepare_session()["status"] == "benchmark_unavailable"
sys_mod.download = lambda *a, **k: S.spy_frame(S.END, 0.0)
sa.expected_session_date = lambda: date(2026, 9, 29)
assert sa.prepare_session()["status"] == "no_new_bar"
assert sa.prepare_session(enforce_session=False)["status"] == "ok"
sa.expected_session_date = lambda: BAR
assert sa.prepare_session()["status"] == "ok"
print("OK prepare_session statuses")
print("E2E screen_ticker PASSED")
