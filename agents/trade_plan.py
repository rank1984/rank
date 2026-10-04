"""
תוכנית עסקה - פונקציה משותפת ל-risk_manager, backtest/engine ו-outcomes.
R = qty * (entry - stop). עמלות ו-slippage לא כלולים ב-R.
"""
import config

_UNSET = object()


def compute_cost_ratio(qty: int, entry: float, stop: float, commission_per_side):
    """(2*עמלה + slippage כניסה + slippage סטופ) / R. None אם העמלה לא הוגדרה."""
    if commission_per_side is None:
        return None
    r = qty * (entry - stop)
    if r <= 0:
        return None
    cost = (
        2 * commission_per_side
        + qty * entry * config.SLIPPAGE_ENTRY_PCT
        + qty * stop * config.SLIPPAGE_STOP_PCT
    )
    return cost / r


def plan_trade(entry_price: float, commission=_UNSET):
    """
    מחזיר dict עם stop/take_profit/qty/risk_dollars/cost_ratio, או None אם אי אפשר לגודל פוזיציה.
    entry_price = המחיר שממנו מחשבים (בלייב: סגירת האות כאינדיקציה; ב-backtest/outcomes: Open של T+1).
    """
    commission_per_side = config.COMMISSION_PER_SIDE if commission is _UNSET else commission
    entry = float(entry_price)
    if entry <= 0:
        return None

    stop = round(entry * (1 - config.STOP_LOSS_PCT), 2)
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return None

    qty_by_risk = int(config.RISK_PER_TRADE_DOLLARS / risk_per_share + 1e-9)
    qty_by_cap = int((config.TOTAL_BUDGET * config.MAX_POSITION_VALUE_PCT) / entry + 1e-9)
    qty = min(qty_by_risk, qty_by_cap)
    if qty < 1:
        return None

    take_profit = round(entry * (1 + config.TAKE_PROFIT_LIVE_PCT), 2)
    risk_dollars = qty * risk_per_share
    cost_ratio = compute_cost_ratio(qty, entry, stop, commission_per_side)
    rr_potential = (qty * (take_profit - entry)) / risk_dollars if risk_dollars > 0 else None

    return {
        "entry_price_plan": round(entry, 4),
        "stop_loss_price": stop,
        "take_profit_price": take_profit,
        "take_profit_pct_used": round(config.TAKE_PROFIT_LIVE_PCT * 100, 1),
        "qty": qty,
        "risk_dollars": round(risk_dollars, 2),
        "position_value": round(qty * entry, 2),
        "cost_ratio": None if cost_ratio is None else round(cost_ratio, 4),
        "rr_potential_gross": None if rr_potential is None else round(rr_potential, 2),
    }
