"""
agents/risk_manager.py - Calculates position sizes and risk limits.
"""

from typing import Dict, Any
import config
from utils import calculate_position_size, logger


class RiskManager:
    def __init__(self, account_size: float = None, risk_pct: float = None):
        self.account_size = account_size or config.DEFAULT_ACCOUNT_SIZE
        self.risk_pct = risk_pct or config.MAX_PORTFOLIO_RISK_PCT

    def size_position(self, trade_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates share size based on trade plan entry and stop loss."""
        ticker = trade_plan.get("ticker")
        entry_price = trade_plan.get("entry_price", 0.0)
        stop_loss = trade_plan.get("stop_loss", 0.0)

        shares = calculate_position_size(
            account_size=self.account_size,
            risk_pct=self.risk_pct,
            entry_price=entry_price,
            stop_loss=stop_loss
        )

        sized_plan = trade_plan.copy()
        sized_plan["shares"] = shares
        sized_plan["position_value"] = round(shares * entry_price, 2)
        sized_plan["risk_amount"] = round(shares * (entry_price - stop_loss), 2)

        logger.info(f"Position sized for {ticker}: {shares} shares (${sized_plan['position_value']})")
        return sized_plan
