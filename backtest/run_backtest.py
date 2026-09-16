"""
נקודת כניסה להרצת Backtest
"""

from datetime import datetime, timedelta
from backtest.engine import run_backtest
from backtest.metrics import calculate_metrics, print_report
import config


def main():
    # 12 חודשים אחורה
    end = datetime.now()
    start = end - timedelta(days=365)

    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    print("=" * 60)
    print("Momentum MAS - Backtest")
    print(f"Period: {start_str} → {end_str}")
    print("=" * 60)

    trades = run_backtest(start_str, end_str)

    metrics = calculate_metrics(trades, initial_capital=config.TOTAL_BUDGET)
    print_report(metrics, start_str, end_str)

    # שומר את העסקאות לקובץ
    if trades:
        import pandas as pd
        df = pd.DataFrame(trades)
        df.to_csv("logs/backtest_trades.csv", index=False)
        print(f"\nנשמרו {len(trades)} עסקאות ב-logs/backtest_trades.csv")


if __name__ == "__main__":
    main()
