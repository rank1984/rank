"""בדיקת count_signals על נתוני דמה (בלי רשת). הרצה: python scripts/test_count_signals.py"""
import _stubs
import _synthetic as S

_stubs.install({}, S.spy_frame())

import pandas as pd  # noqa: E402

import count_signals as cs  # noqa: E402

strong, weak = S.make_strong(), S.make_weak()
spy = S.spy_full(strong)
data = {"SPY": spy, "STRONG": strong, "WEAK": weak}
start = strong.index[-12]

rows = cs.evaluate_window(data, spy, start, None, use_mcap=False)
cands = [r for r in rows if r["passed"]]
assert [(c["ticker"], c["bar_date"]) for c in cands] == [("STRONG", "2026-09-28")], cands
print("OK exactly one candidate on the gap day:", cands[0]["ticker"], cands[0]["bar_date"])

fun = cs.funnel(rows, use_mcap=False)
assert fun["remaining_after_cumulative"].iloc[-1] == len(cands)
assert "market_cap_out_of_range" not in fun["filter"].tolist()
print("OK funnel consistent with candidates (no mcap rows when use_mcap=False)")

# עם mcap: fail-closed כשחסר
infos = {"STRONG": (300e6, 50e6), "WEAK": (300e6, 50e6)}
rows2 = cs.evaluate_window(data, spy, start, infos, use_mcap=True)
assert sum(r["passed"] for r in rows2) == 1 and all(r["lookahead_mcap_float"] == 1 for r in rows2)
rows3 = cs.evaluate_window(data, spy, start, {}, use_mcap=True)
assert sum(r["passed"] for r in rows3) == 0
assert any("missing_mcap_or_float" in r["all_failed"] for r in rows3 if r["ticker"] == "STRONG")
print("OK mcap run: look-ahead flag, fail-closed when info missing")

text = cs.summarize("test", rows, fun, ["BAD"])
assert "מועמדים טכניים בסך הכל: 1" in text and "BAD" in text
print("OK summary text")

# דטרמיניזם
assert cs.evaluate_window(data, spy, start, None, False) == rows
print("OK deterministic")
print("test_count_signals PASSED")
