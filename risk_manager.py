"""
סוכן 3: Risk & Yield Manager
- Position Sizing מבוסס-סיכון: qty = RISK_PER_TRADE_DOLLARS / (entry - stop)
- דורש דירוג קטליזטור A או B (לא C/D) לפי ברירת המחדל
- מחשב עמלות + מס רווחי הון בישראל ומוודא יחס סיכון:סיכוי נטו >= 1:3
"""

import config

TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def catalyst_tier_acceptable(tier: str) -> bool:
    return TIER_ORDER.get(tier, 99) <= TIER_ORDER.get(config.CATALYST_TIER_MIN_ACCEPTABLE, 1)


def evaluate_trade(candidate: dict) -> dict:
    """מקבל מועמד (אחרי סינון טכני + קטליזטור) ומחזיר החלטת מסחר מלאה"""
    price = candidate["price"]
    catalyst_tier = candidate.get("catalyst_tier", "D")

    if config.REQUIRE_NEWS and not catalyst_tier_acceptable(catalyst_tier):
        return {
            **candidate,
            "approved": False,
            "reason": f"catalyst_tier_{catalyst_tier}_below_minimum_{config.CATALYST_TIER_MIN_ACCEPTABLE}",
        }

    entry_price = price
    stop_loss_price = round(entry_price * (1 - config.STOP_LOSS_PCT), 2)
    risk_per_share = entry_price - stop_loss_price

    if risk_per_share <= 0:
        return {**candidate, "approved": False, "reason": "invalid_risk_per_share"}

    # --- Position Sizing מבוסס-סיכון (השדרוג המרכזי) ---
    qty_by_risk = int(config.RISK_PER_TRADE_DOLLARS // risk_per_share)

    max_value_qty = int((config.TOTAL_BUDGET * config.MAX_POSITION_VALUE_PCT) // entry_price)
    qty = min(qty_by_risk, max_value_qty)

    if qty < 1:
        return {**candidate, "approved": False, "reason": "position_too_small_for_risk_budget"}

    actual_position_value = round(qty * entry_price, 2)

    take_profit_pct = (
        config.TAKE_PROFIT_MAX_PCT if catalyst_tier == "A" else config.TAKE_PROFIT_MIN_PCT
    )
    take_profit_price = round(entry_price * (1 + take_profit_pct), 2)

    total_commission = config.COMMISSION_PER_TRADE * 2

    gross_profit = qty * (take_profit_price - entry_price)
    net_profit_before_tax = gross_profit - total_commission
    tax_on_gain = max(0, net_profit_before_tax * config.CAPITAL_GAINS_TAX_RATE)
    net_profit_after_tax = round(net_profit_before_tax - tax_on_gain, 2)

    gross_loss = qty * risk_per_share
    net_loss = round(gross_loss + total_commission, 2)

    risk_reward = round(net_profit_after_tax / net_loss, 2) if net_loss > 0 else 0

    approved = risk_reward >= config.MIN_RISK_REWARD and net_profit_after_tax > 0

    return {
        **candidate,
        "approved": approved,
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "take_profit_pct_used": round(take_profit_pct * 100, 1),
        "qty": qty,
        "risk_dollars": round(qty * risk_per_share, 2),
        "position_value": actual_position_value,
        "total_commission": round(total_commission, 2),
        "net_profit_after_tax": net_profit_after_tax,
        "net_loss_if_stopped": net_loss,
        "risk_reward_net": risk_reward,
        "reason": "approved" if approved else "risk_reward_below_threshold_or_unprofitable",
    }


def run_risk_manager(candidates: list) -> list:
    results = []
    for c in candidates:
        result = evaluate_trade(c)
        status = "✓ אושר" if result["approved"] else "✗ נדחה"
        print(
            f"  {status} {c['ticker']} (קטליזטור {c.get('catalyst_tier', '?')}): "
            f"R:R נטו={result.get('risk_reward_net', 'N/A')}, "
            f"סיכון=${result.get('risk_dollars', 'N/A')}, "
            f"רווח נטו אם מוצלח=${result.get('net_profit_after_tax', 'N/A')} | {result['reason']}"
        )
        results.append(result)
    return results
