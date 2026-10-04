"""
בדיקות ה-backtest/outcomes ותוכנית העסקה (בדיקות 5-8, 10-11 ועוד):
gap דרך סטופ, סטופ לפני יעד, כניסה ב-Open, pending, plan_trade זהה ב-live וב-backtest,
שער עלות, כלל בחירה וקיבולת, fallback לא מאושר, מיגרציית לוג.
הרצה: python scripts/test_trade_sim.py
"""
import _stubs
import os
import tempfile

import pandas as pd

import _synthetic as S

_stubs.install({}, S.spy_frame())   # backtest.engine מייבא yfinance

import config
from agents.risk_manager import apply_portfolio_rules, evaluate_trade
from agents.trade_plan import plan_trade
from backtest.engine import mark_portfolio_selection, simulate_trade
from utils import append_rows, read_header

Z = dict(slip_entry=0.0, slip_stop=0.0, slip_tp=0.0)


def frame(rows):
    idx = pd.bdate_range(end="2026-09-28", periods=len(rows))
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"], index=idx)


def cand(df, pos=0, price=None):
    return {"ticker": "T", "date": df.index[pos], "price": price or float(df["Close"].iloc[pos]),
            "rvol": 4.0, "relative_strength_pct": 5.0, "rsi": 60.0, "gap_pct": 8.0, "atr_pct": 4.0}


V = 1_000_000
# --- 7. כניסה ב-Open של T+1 (לא Close של האות) ---
df = frame([(10, 10, 10, 10, V), (10.5, 10.6, 10.4, 10.5, V), (10.5, 10.6, 10.4, 10.5, V), (10.5, 10.6, 10.4, 10.5, V)])
r = simulate_trade(cand(df), df, **Z)
assert r["status"] == "closed" and r["entry_price"] == 10.5, r
assert r["entry_gap_vs_signal_close_pct"] == 5.0
assert r["exit_reason"] == "time_exit" and r["days_held"] == 3
print("OK entry = Open of T+1, time_exit after 3 days")

# --- 5. gap דרך הסטופ: יציאה בפתיחה, R < -1 ---
df = frame([(10, 10, 10, 10, V), (10, 10.1, 9.9, 10, V), (9.0, 9.1, 8.8, 8.9, V), (9, 9, 9, 9, V)])
r = simulate_trade(cand(df), df, **Z)
assert r["exit_reason"] == "stop_gap" and r["exit_price"] == 9.0, r
assert r["r_multiple_gross"] < -1.0, r["r_multiple_gross"]
print("OK stop_gap exits at open, R =", r["r_multiple_gross"])

# --- 6. סטופ ויעד באותו נר: יוצא סטופ ---
df = frame([(10, 10, 10, 10, V), (10, 11.5, 9.5, 10, V), (10, 10, 10, 10, V), (10, 10, 10, 10, V)])
r = simulate_trade(cand(df), df, **Z)
assert r["exit_reason"] == "stop_loss" and r["days_held"] == 1 and r["r_multiple_gross"] == -1.0, r
print("OK stop before TP on same bar; entry day is included in window")

# --- יעד ---
df = frame([(10, 10, 10, 10, V), (10, 11.3, 9.9, 11, V), (10, 10, 10, 10, V), (10, 10, 10, 10, V)])
r = simulate_trade(cand(df), df, **Z)
assert r["exit_reason"] == "take_profit" and r["exit_price"] == 11.2 and r["r_multiple_gross"] == 3.0, r
print("OK take_profit at +12% = 3.0R gross")

# --- gap מעל היעד ---
df = frame([(10, 10, 10, 10, V), (10, 10.2, 9.9, 10, V), (12.0, 12.5, 11.9, 12.2, V), (10, 10, 10, 10, V)])
r = simulate_trade(cand(df), df, **Z)
assert r["exit_reason"] == "take_profit_gap" and r["exit_price"] == 12.0, r
print("OK take_profit_gap exits at open")

# --- pending: אות בנר האחרון / נרות לא מספיקים ---
df = frame([(10, 10, 10, 10, V), (10, 10.1, 9.9, 10, V)])
assert simulate_trade(cand(df, pos=1), df, **Z)["status"] == "pending"
assert simulate_trade(cand(df, pos=0), df, **Z)["status"] == "pending"   # נר אחד בלבד מתוך 3
print("OK pending when data is missing (no forced close)")

# --- slippage מחמיר את התוצאה ---
df = frame([(10, 10, 10, 10, V), (10, 11.3, 9.9, 11, V), (10, 10, 10, 10, V), (10, 10, 10, 10, V)])
r0 = simulate_trade(cand(df), df, **Z)
r1 = simulate_trade(cand(df), df)  # slippage מה-config
assert r1["pnl_gross"] < r0["pnl_gross"]
print("OK slippage reduces pnl")

# --- 8. plan_trade זהה בין risk_manager ל-backtest ---
for price in (5.0, 8.4, 10.0, 17.3, 30.0):
    p = plan_trade(price)
    out = evaluate_trade({"ticker": "X", "price": price, "catalyst_tier": "A", "classifier_source": "llm", "atr_pct": 5.0})
    for k in ("stop_loss_price", "take_profit_price", "qty", "risk_dollars", "position_value"):
        assert p[k] == out[k], (price, k, p[k], out[k])
df = frame([(10, 10, 10, 10, V), (10.0, 10.1, 9.9, 10, V), (10, 10.1, 9.9, 10, V), (10, 10.1, 9.9, 10, V)])
r = simulate_trade(cand(df), df, **Z)
p = plan_trade(10.0)
assert (r["qty"], r["stop"], r["take_profit"]) == (p["qty"], p["stop_loss_price"], p["take_profit_price"])
print("OK plan_trade identical in risk_manager and backtest")

# --- שער עלות (בדיקה 10 + בדיקת שפיות לקונפיג) ---
cfg_c = config.COMMISSION_PER_SIDE
config.COMMISSION_PER_SIDE = None
assert plan_trade(10.0)["cost_ratio"] is None
config.COMMISSION_PER_SIDE = 3.0
assert plan_trade(10.0)["cost_ratio"] > config.MAX_COST_RATIO
config.COMMISSION_PER_SIDE = 0.5
assert plan_trade(10.0)["cost_ratio"] <= config.MAX_COST_RATIO
config.COMMISSION_PER_SIDE = cfg_c
print("OK cost_ratio None / fail / pass")


def sig(ticker, rvol, rs=5.0, tier="A", source="llm", price=10.0):
    return evaluate_trade({"ticker": ticker, "price": price, "catalyst_tier": tier, "classifier_source": source,
                           "rvol": rvol, "relative_strength_pct": rs, "atr_pct": 5.0})


# --- עמלה לא מוגדרת: approved_signal כן, approved_live לא ---
config.COMMISSION_PER_SIDE = None
res = apply_portfolio_rules([sig("AAA", 4.0)], open_positions={})
assert res[0]["approved_signal"] and not res[0]["approved_live"] and res[0]["reason"] == "commission_not_set"
print("OK commission None -> approved_signal only")

# --- שער עלות נכשל ---
config.COMMISSION_PER_SIDE = 3.0
res = apply_portfolio_rules([sig("AAA", 4.0)], open_positions={})
assert res[0]["approved_signal"] and res[0]["cost_gate_pass"] is False
assert not res[0]["approved_live"] and res[0]["reason"] == "cost_gate_failed"
print("OK cost gate failed -> not live, still measured (approved_signal)")

# --- 11. כלל בחירה: 4 אותות -> 2 נבחרים לפי RVOL, 2 skipped_capacity ---
config.COMMISSION_PER_SIDE = 0.5
res = apply_portfolio_rules([sig("D", 3.5), sig("A", 6.0), sig("C", 4.0), sig("B", 5.0)], open_positions={})
live = sorted(r["ticker"] for r in res if r["approved_live"])
skipped = sorted(r["ticker"] for r in res if r["skipped_capacity"] == 1)
assert live == ["A", "B"] and skipped == ["C", "D"], (live, skipped)
print("OK rank rule: live", live, "skipped_capacity", skipped)

# --- פוזיציה פתוחה תופסת מקום ושוללת אותו טיקר ---
res = apply_portfolio_rules([sig("A", 6.0), sig("B", 5.0)], open_positions={"X": {"qty": 10, "value": 100.0}})
assert [r["ticker"] for r in res if r["approved_live"]] == ["A"]
res = apply_portfolio_rules([sig("A", 6.0)], open_positions={"A": {"qty": 10, "value": 100.0}})
assert res[0]["reason"] == "already_open"
print("OK open positions respected")

# --- Tier B / fallback לא מאושרים כאות ---
config.COMMISSION_PER_SIDE = cfg_c
assert not sig("B1", 4.0, tier="B")["approved_signal"]
fb = sig("F1", 4.0, source="keyword_fallback")
assert not fb["approved_signal"] and fb["reason"] == "classifier_keyword_fallback_not_approved"
assert fb["qty"] >= 1 and fb["stop_loss_price"] > 0   # תוכנית מחושבת גם לנדחה (outcome היפותטי)
print("OK Tier B and fallback are not approved_signal, plan still computed")

# --- בחירה פורטפוליו ב-backtest ---
trades = [
    {"ticker": "A", "entry_date": "2026-09-01", "exit_date": "2026-09-03", "rvol": 5, "relative_strength_pct": 3},
    {"ticker": "B", "entry_date": "2026-09-01", "exit_date": "2026-09-02", "rvol": 4, "relative_strength_pct": 3},
    {"ticker": "C", "entry_date": "2026-09-01", "exit_date": "2026-09-02", "rvol": 3.5, "relative_strength_pct": 3},
    {"ticker": "D", "entry_date": "2026-09-04", "exit_date": "2026-09-05", "rvol": 3.5, "relative_strength_pct": 3},
]
out = {t["ticker"]: t["portfolio_selected"] for t in mark_portfolio_selection(trades)}
assert out == {"A": 1, "B": 1, "C": 0, "D": 1}, out
print("OK backtest portfolio selection")

# --- מיגרציית כותרת ישנה ---
with tempfile.TemporaryDirectory() as d:
    path, legacy = os.path.join(d, "decisions.csv"), os.path.join(d, "legacy.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("timestamp,ticker,approved\n2026-01-01,AAA,True\n")
    append_rows(path, ["run_id", "ticker"], [{"run_id": "r1", "ticker": "BBB"}], legacy_path=legacy)
    assert read_header(path) == ["run_id", "ticker"] and os.path.exists(legacy)
    assert "AAA" in open(legacy, encoding="utf-8").read()
print("OK legacy log header migration")
print("test_trade_sim PASSED")
