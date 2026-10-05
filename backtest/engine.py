"""
backtest/engine.py - Simulation engine for backtesting momentum strategies.
"""

from typing import List, Dict, Any
import pandas as pd
from utils import logger

class BacktestEngine:
    def __init__(self, initial_capital: float = 10000.0, commission_per_share: float = 0.005):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.commission_per_share = commission_per_share
        self.trades_history = []
        self.portfolio_selections = []

    def mark_portfolio_selection(self, date: str, candidates: List[Dict[str, Any]], selected: List[Dict[str, Any]]):
        """Records candidate selections per trading session for audit/stats."""
        self.portfolio_selections.append({
            "date": date,
            "total_candidates": len(candidates),
            "selected_count": len(selected),
            "selected_tickers": [s.get("ticker") for s in selected]
        })

    def execute_trade(self, date: str, ticker: str, side: str, shares: int, price: float, reason: str = "") -> Dict[str, Any]:
        """Executes a simulated trade and updates balance/history."""
        gross_cost = shares * price
        commission = shares * self.commission_per_share
        
        if side.upper() == "BUY":
            net_cost = gross_cost + commission
            self.capital -= net_cost
        else:
            net_cost = gross_cost - commission
            self.capital += net_cost

        trade_record = {
            "date": date,
            "ticker": ticker,
            "side": side.upper(),
            "shares": shares,
            "price": price,
            "commission": commission,
            "cash_after": self.capital,
            "reason": reason
        }
        self.trades_history.append(trade_record)
        return trade_record

    def run_simulation(self, market_data: Dict[str, pd.DataFrame], trade_plans: List[Dict[str, Any]]) -> pd.DataFrame:
        """Runs the simulation across historical trade plans."""
        logger.info(f"Starting backtest simulation over {len(trade_plans)} trade plans...")
        for plan in trade_plans:
            ticker = plan["ticker"]
            date = plan.get("date", "UNKNOWN")
            shares = plan.get("shares", 0)
            entry_price = plan.get("entry_price", 0.0)
            target_price = plan.get("target_price", 0.0)
            stop_loss = plan.get("stop_loss", 0.0)

            if shares <= 0 or ticker not in market_data:
                continue

            df = market_data[ticker]
            # Execute Entry
            self.execute_trade(date, ticker, "BUY", shares, entry_price, reason="Entry Plan")

            # Check Exit Conditions against subsequent price bars
            exit_price = target_price  # Default target exit for stub
            exit_reason = "Target Hit"
            
            for _, row in df.iterrows():
                if row.get("low", entry_price) <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "Stop Loss Hit"
                    break
                elif row.get("high", entry_price) >= target_price:
                    exit_price = target_price
                    exit_reason = "Target Hit"
                    break

            self.execute_trade(date, ticker, "SELL", shares, exit_price, reason=exit_reason)

        return pd.DataFrame(self.trades_history)
