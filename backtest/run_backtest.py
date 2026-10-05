"""
backtest/run_backtest.py - Script to execute backtest simulations.
"""

import argparse
from typing import Dict, Any, List
import pandas as pd

from backtest.engine import BacktestEngine
from backtest.stats import calculate_performance_stats
from utils import logger


def run_backtest_simulation(
    market_data: Dict[str, pd.DataFrame],
    trade_plans: List[Dict[str, Any]],
    initial_capital: float = 10000.0,
    commission_per_share: float = 0.005
) -> Dict[str, Any]:
    """Runs a backtest simulation and returns trades and summary performance stats."""
    engine = BacktestEngine(initial_capital=initial_capital, commission_per_share=commission_per_share)
    trades_df = engine.run_simulation(market_data, trade_plans)
    stats = calculate_performance_stats(trades_df, initial_capital=initial_capital)
    
    return {
        "trades": trades_df,
        "stats": stats,
        "portfolio_selections": engine.portfolio_selections
    }


def main():
    parser = argparse.ArgumentParser(description="Run Momentum MAS Backtest Simulation")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial account capital")
    parser.add_argument("--commission", type=float, default=0.005, help="Commission cost per share")
    args = parser.parse_args()

    logger.info(f"Initiating Backtest Runner with Capital=${args.capital}, Commission=${args.commission}")
    
    # Example placeholder backtest execution
    results = run_backtest_simulation(market_data={}, trade_plans=[], initial_capital=args.capital, commission_per_share=args.commission)
    logger.info("Backtest execution finished.")
    print("Backtest Stats:", results["stats"])


if __name__ == "__main__":
    main()
