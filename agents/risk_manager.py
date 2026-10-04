"""
סוכן 3: Risk & Yield Manager

הפרדה בין מדידה לביצוע:
  approved_signal = עבר Screener + Tier A (+ סיווג LLM, לא fallback)  <- מה שנמדד ל-Edge
  approved_live   = approved_signal + שער עלות + קיבולת פורטפוליו    <- מה שנשלח לביצוע

- התוכנית (entry/stop/tp/qty/cost_ratio) מחושבת *לפני* כל דחייה, כדי שגם נדחים יקבלו outcome היפותטי.
- שער R:R בוטל כתנאי אישור. rr_potential_gross נרשם כמידע בלבד.
- COMMISSION_PER_SIDE=None -> אין approved_live (reason=commission_not_set).
"""
import csv
import os

import config
from agents.trade_plan import plan_trade

TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def catalyst_tier_acceptable(tier: str) -> bool:
    return TIER_ORDER.get(tier, 99) <= TIER_ORDER.get(config.CATALYST_TIER_MIN_ACCEPTABLE, 0)


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def evaluate_trade(candidate: dict) -> dict:
    """החלטת אות (approved_signal) + תוכנית + cost_ratio. קיבולת מטופלת ב-apply_portfolio_rules."""
    price = candidate["price"]
    tier = candidate.get("catalyst_tier", "D")
    source = candidate.get("classifier_source", "llm")

    out = {
        **candidate,
        "strategy_version": config.STRATEGY_VERSION,
        "entry_basis": config.ENTRY_BASIS,
        "approved_signal": False,
        "approved_live": False,
        "cost_gate_pass": None,
        "skipped_capacity": 0,
        "reason": "",
    }

    plan = plan_trade(price)
    if plan:
        out.update(plan)
        atr_pct = _f(candidate.get("atr_pct"))
        out["stop_atr_ratio"] = round(config.STOP_LOSS_PCT * 100 / atr_pct, 2) if atr_pct > 0 else None

    reason = None
    if plan is None:
        reason = "position_too_small_for_risk_budget"
    elif config.REQUIRE_NEWS and not catalyst_tier_acceptable(tier):
        reason = f"catalyst_tier_{tier}_below_minimum_{config.CATALYST_TIER_MIN_ACCEPTABLE}"
    elif source != "llm" and not config.ALLOW_FALLBACK_APPROVAL:
        reason = f"classifier_{source}_not_approved"

    if reason is None:
        out["approved_signal"] = True
        out["reason"] = "approved_signal"
        if plan["cost_ratio"] is not None:
            out["cost_gate_pass"] = bool(plan["cost_ratio"] <= config.MAX_COST_RATIO)
    else:
        out["reason"] = reason
        if plan and plan["cost_ratio"] is not None:
            out["cost_gate_pass"] = bool(plan["cost_ratio"] <= config.MAX_COST_RATIO)
    return out


def open_positions_from_fills(path: str | None = None) -> dict:
    """{ticker: {"qty": net_qty, "value": ערך משוער}} לפי fills.csv (status=filled)."""
    path = path or config.FILLS_FILE
    pos = {}
    if not os.path.isfile(path):
        return pos
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("status") or "").strip().lower() != "filled":
                continue
            t = (row.get("ticker") or "").upper().strip()
            side = (row.get("side") or "").lower().strip()
            qty = _f(row.get("qty"))
            price = _f(row.get("price"))
            if not t or qty <= 0:
                continue
            p = pos.setdefault(t, {"qty": 0.0, "last_buy_price": 0.0})
            if side == "buy":
                p["qty"] += qty
                p["last_buy_price"] = price
            elif side == "sell":
                p["qty"] -= qty
    return {t: {"qty": v["qty"], "value": v["qty"] * v["last_buy_price"]}
            for t, v in pos.items() if v["qty"] > 0}


def _rank_key(r: dict):
    # RANK_RULE = rvol_desc, rs_desc, ticker_asc
    return (-_f(r.get("rvol")), -_f(r.get("relative_strength_pct")), r.get("ticker", ""))


def apply_portfolio_rules(results: list, open_positions: dict | None = None) -> list:
    """קובע approved_live: עמלה מוגדרת, שער עלות, קיבולת (MAX_OPEN_POSITIONS + תקציב), פוזיציה פתוחה."""
    open_positions = open_positions_from_fills() if open_positions is None else open_positions
    slots = config.MAX_OPEN_POSITIONS - len(open_positions)
    cash = config.TOTAL_BUDGET - sum(p["value"] for p in open_positions.values())

    eligible = [r for r in results if r["approved_signal"]]
    eligible.sort(key=_rank_key)

    for i, r in enumerate(eligible, start=1):
        r["rank_position"] = i
        if config.COMMISSION_PER_SIDE is None:
            r["reason"] = "commission_not_set"
        elif r.get("cost_gate_pass") is not True:
            r["reason"] = "cost_gate_failed"
        elif r["ticker"] in open_positions:
            r["reason"] = "already_open"
        elif slots <= 0 or _f(r.get("position_value")) > cash:
            r["reason"] = "skipped_capacity"
            r["skipped_capacity"] = 1
        else:
            r["approved_live"] = True
            r["reason"] = "approved_live"
            slots -= 1
            cash -= _f(r.get("position_value"))
    return results


def run_risk_manager(candidates: list) -> list:
    results = [evaluate_trade(c) for c in candidates]
    apply_portfolio_rules(results)
    for r in results:
        if r["approved_live"]:
            status = "✓ לביצוע"
        elif r["approved_signal"]:
            status = "◐ אות בלבד"
        else:
            status = "✗ נדחה"
        print(
            f"  {status} {r['ticker']} (קטליזטור {r.get('catalyst_tier', '?')}): "
            f"cost_ratio={r.get('cost_ratio', 'N/A')}, סיכון=${r.get('risk_dollars', 'N/A')}, "
            f"rr_potential={r.get('rr_potential_gross', 'N/A')} | {r['reason']}"
        )
    return results
