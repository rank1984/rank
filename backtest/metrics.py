"""
חישוב מדדי ביצועים ל-Backtest
"""

import pandas as pd
import numpy as np


def calculate_metrics(trades: list, initial_capital: float = 1000.0) -> dict:
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_rr": 0.0,
            "total_net_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "final_capital": initial_capital,
            "return_pct": 0.0,
        }

    df = pd.DataFrame(trades)

    wins = df[df["net_pnl"] > 0]
    losses = df[df["net_pnl"] <= 0]

    total_trades = len(df)
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0

    gross_profit = wins["net_pnl"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["net_pnl"].sum()) if len(losses) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    avg_rr = df["realized_rr"].mean() if "realized_rr" in df.columns else 0

    # Equity curve + Max Drawdown
    df = df.sort_values("entry_date")
    df["cumulative_pnl"] = df["net_pnl"].cumsum()
    df["equity"] = initial_capital + df["cumulative_pnl"]

    peak = df["equity"].cummax()
    drawdown = (df["equity"] - peak) / peak
    max_drawdown_pct = abs(drawdown.min()) * 100 if len(drawdown) > 0 else 0

    final_capital = df["equity"].iloc[-1]
    return_pct = (final_capital - initial_capital) / initial_capital * 100

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "avg_rr": round(avg_rr, 2),
        "total_net_pnl": round(df["net_pnl"].sum(), 2),
        "max_drawdown_pct": round(max_drawdown_pct, 1),
        "final_capital": round(final_capital, 2),
        "return_pct": round(return_pct, 1),
        "avg_days_held": round(df["days_held"].mean(), 1) if "days_held" in df.columns else 0,
    }


def print_report(metrics: dict, start_date: str, end_date: str):
    print("\n" + "=" * 60)
    print("BACKTEST REPORT")
    print("=" * 60)
    print(f"Period          : {start_date} → {end_date}")
    print(f"Total Trades    : {metrics['total_trades']}")
    print(f"Win Rate        : {metrics['win_rate']}%")
    print(f"Profit Factor   : {metrics['profit_factor']}")
    print(f"Avg Realized R:R: {metrics['avg_rr']}")
    print(f"Total Net P&L   : ${metrics['total_net_pnl']}")
    print(f"Max Drawdown    : {metrics['max_drawdown_pct']}%")
    print(f"Final Capital   : ${metrics['final_capital']}")
    print(f"Return          : {metrics['return_pct']}%")
    print(f"Avg Days Held   : {metrics['avg_days_held']}")
    print("=" * 60)
