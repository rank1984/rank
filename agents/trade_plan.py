"""
agents/trade_plan.py - Generates structured trade execution plans.
"""

from typing import Dict, Any
from utils import logger


class TradePlanGenerator:
    def __init__(self, default_stop_pct: float = 0.05, default_target_pct: float = 0.15):
        self.default_stop_pct = default_stop_pct
        self.default_target_pct = default_target_pct

    def create_plan(self, candidate: Dict[str, Any], catalyst_info: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a trade plan with entry, stop loss, and target prices."""
        ticker = candidate["ticker"]
        entry_price = candidate.get("price", 0.0)
        
        stop_loss = round(entry_price * (1.0 - self.default_stop_pct), 2)
        target_price = round(entry_price * (1.0 + self.default_target_pct), 2)

        plan = {
            "ticker": ticker,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_price": target_price,
            "catalyst": catalyst_info.get("headline", ""),
            "catalyst_score": catalyst_info.get("score", 0.0),
            "status": "APPROVED"
        }

        logger.info(f"Created trade plan for {ticker}: Entry=${entry_price}, Stop=${stop_loss}, Target=${target_price}")
        return plan
