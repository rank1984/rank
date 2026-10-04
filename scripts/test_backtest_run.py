"""run_backtest מקצה לקצה על נתוני דמה: סינון -> כניסה ב-Open של T+1 -> יציאה -> בחירת פורטפוליו."""
import _stubs
import _synthetic as S

_stubs.install({}, S.spy_frame())

import pandas as pd  # noqa: E402

import config  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from backtest.stats import bootstrap_ci_mean  # noqa: E402

strong = S.make_strong()
sig_close = float(strong["Close"].iloc[-1])
future_idx = pd.bdate_range(start=strong.index[-1] + pd.Timedelta(days=1), periods=4)
entry_open = round(sig_close * 1.01, 2)
future = pd.DataFrame({
    "Open": [entry_open, entry_open * 1.05, entry_open, entry_open],
    "High": [entry_open * 1.13, entry_open * 1.06, entry_open, entry_open],     # יום 1 פוגע ביעד 12%
    "Low": [entry_open * 0.99, entry_open * 1.02, entry_open, entry_open],
    "Close": [entry_open * 1.10, entry_open * 1.05, entry_open, entry_open],
    "Volume": [3e6] * 4,
}, index=future_idx)
df = pd.concat([strong, future])
spy = S.spy_full(df)

trades = run_backtest("2026-01-01", "2026-12-31", data={"SPY": spy, "STRONG": df}, sensitivity=0.0)
assert len(trades) == 1, trades
t = trades[0]
assert t["signal_date"] == "2026-09-28" and t["entry_price"] == entry_open, t
assert t["exit_reason"] == "take_profit" and t["days_held"] == 1, t
assert t["portfolio_selected"] == 1
assert abs(t["entry_gap_vs_signal_close_pct"] - 1.0) < 0.05
assert t["r_multiple_net"] is None or config.COMMISSION_PER_SIDE is not None
print("OK run_backtest end-to-end:", {k: t[k] for k in ("signal_date", "entry_price", "exit_reason", "r_multiple_gross")})

# רגישות ל-slippage מורידה את התוצאה
worse = run_backtest("2026-01-01", "2026-12-31", data={"SPY": spy, "STRONG": df}, sensitivity=3.0)[0]
assert worse["r_multiple_gross"] < t["r_multiple_gross"]
print("OK slippage sensitivity x3 lowers R:", t["r_multiple_gross"], "->", worse["r_multiple_gross"])

lo, mean, hi = bootstrap_ci_mean([1.0, -1.0, 3.0, -1.0, 0.5, -1.0, 2.0])
assert lo <= mean <= hi
assert bootstrap_ci_mean([]) is None
print("OK bootstrap CI")

# count_signals --with-outcomes (נר אחרון = pending, לא קורס)
import tempfile, os  # noqa: E402
import count_signals as cs  # noqa: E402
cand = [{"ticker": "STRONG", "bar_date": "2026-09-25", "price": 10.0, "rvol": 4.0, "relative_strength_pct": 5.0,
         "rsi": 60.0, "gap_pct": 8.0, "atr_pct": 4.0}]
with tempfile.TemporaryDirectory() as d:
    txt = cs.outcomes_text({"STRONG": df}, cand, os.path.join(d, "o.csv"))
    assert "DESCRIPTIVE_ONLY" in txt
print("OK count_signals outcomes path")
print("test_backtest_run PASSED")
