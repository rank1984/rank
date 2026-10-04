"""בדיקות יחידה לפילטרים (כל פילטר לחוד) ולשעון השוק. הרצה: python scripts/test_p0_filters.py"""
import _stubs  # noqa: F401
from datetime import date, datetime

import config
import _synthetic as S
from agents.filters import add_indicators, evaluate_filters, features_at
from utils import NY, expected_session_date

df = add_indicators(S.make_strong())
BASE = features_at(df, len(df) - 1, 0.0)
MC, FL = 300e6, 50e6

assert evaluate_filters(BASE, MC, FL) == [], f"מקרה חיובי נכשל: {evaluate_filters(BASE, MC, FL)}"
print("OK strong passes all filters")

cases = [
    ("price_out_of_range", {"price": 3.0}, MC, FL),
    ("price_out_of_range", {"price": 45.0}, MC, FL),
    ("dollar_volume_too_low", {"dollar_volume": 1e6}, MC, FL),
    ("gap_out_of_range", {"gap_pct": 0.30}, MC, FL),
    ("gap_out_of_range", {"gap_pct": 0.02}, MC, FL),
    ("gap_out_of_range", {"gap_pct": -0.08}, MC, FL),
    ("no_ema_breakout", {"ema_breakout": False}, MC, FL),
    ("below_ema_trend", {"above_ema_trend": False}, MC, FL),
    ("rsi_out_of_range", {"rsi": 40.0}, MC, FL),
    ("rsi_out_of_range", {"rsi": 78.0}, MC, FL),
    ("rsi_out_of_range", {"rsi": None}, MC, FL),
    ("rvol_too_low", {"rvol": 1.0}, MC, FL),
    ("atr_out_of_range", {"atr_pct": 0.01}, MC, FL),
    ("atr_out_of_range", {"atr_pct": 0.30}, MC, FL),
    ("atr_out_of_range", {"atr_pct": None}, MC, FL),
    ("weak_relative_strength", {"relative_strength": 0.01}, MC, FL),
    ("weak_relative_strength", {"relative_strength": None}, MC, FL),
    ("missing_mcap_or_float", {}, None, FL),
    ("missing_mcap_or_float", {}, MC, None),
    ("missing_mcap_or_float", {}, None, None),
    ("market_cap_out_of_range", {}, 5e9, FL),
    ("market_cap_out_of_range", {}, 10e6, FL),
    ("float_out_of_range", {}, MC, 500e6),
    ("float_out_of_range", {}, MC, 1e6),
]
for name, override, mc, fl in cases:
    f = {**BASE, **override}
    failed = evaluate_filters(f, mc, fl)
    assert failed == [name], f"{name} {override} mc={mc} fl={fl} -> {failed}"
print(f"OK {len(cases)} single-filter cases each rejected for exactly one reason")

weak = add_indicators(S.make_weak())
fw = features_at(weak, len(weak) - 1, 0.0)
failed = evaluate_filters(fw, MC, FL)
for must in ("no_ema_breakout", "rsi_out_of_range", "rvol_too_low"):
    assert must in failed, (must, failed)
print("OK weak data fails multiple filters:", ",".join(failed))

# מצב שאינו GAP_REQUIRE_POSITIVE
config.GAP_REQUIRE_POSITIVE = False
assert evaluate_filters({**BASE, "gap_pct": -0.08}, MC, FL) == []
config.GAP_REQUIRE_POSITIVE = True
print("OK gap sign handling")

# check_mcap_float=False מדלג על פילטרי mcap/float
assert evaluate_filters(BASE, None, None, check_mcap_float=False) == []
print("OK check_mcap_float=False")

# שעון שוק
def ny(y, m, d, h, mi):
    return datetime(y, m, d, h, mi, tzinfo=NY)

assert expected_session_date(ny(2026, 10, 3, 12, 0)) == date(2026, 10, 2)    # שבת -> שישי
assert expected_session_date(ny(2026, 10, 4, 12, 0)) == date(2026, 10, 2)    # ראשון -> שישי
assert expected_session_date(ny(2026, 9, 28, 10, 0)) == date(2026, 9, 25)    # שני בבוקר -> שישי
assert expected_session_date(ny(2026, 9, 28, 17, 0)) == date(2026, 9, 28)    # שני אחרי סגירה
assert expected_session_date(ny(2026, 9, 29, 16, 10)) == date(2026, 9, 28)   # בתוך ה-buffer
assert expected_session_date(ny(2026, 9, 29, 16, 30)) == date(2026, 9, 29)
print("OK expected_session_date")
print("test_p0_filters PASSED")
