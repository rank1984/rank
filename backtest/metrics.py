"""
כל המדדים לדוח. כולל הגנת 0 עסקאות.
"""
import numpy as np
import pandas as pd


def _longest_losing_streak(r_series: pd.Series) -> int:
    longest = cur = 0
    for r in r_series.tolist():
        if r < 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return longest


def _max_drawdown_r(r_series: pd.Series) -> float:
    if r_series.empty:
        return 0.0
    equity = np.cumsum(r_series.values)
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    return float(dd.min())


def calculate_metrics(trades_df: pd.DataFrame) -> dict:
    base = {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "avg_win_r": 0.0,
        "avg_loss_r": 0.0,
        "expectancy_r": 0.0,
        "profit_factor": 0.0,
        "total_r": 0.0,
        "max_drawdown_r": 0.0,
        "longest_losing_streak": 0,
        "avg_bars_held": 0.0,
        "avg_slippage_bps": 0.0,
    }
    if trades_df is None or trades_df.empty:
        return base

    df = trades_df
    wins = df[df["r_multiple"] > 0]
    losses = df[df["r_multiple"] <= 0]

    gross_win = float(wins["r_multiple"].sum())
    gross_loss = float(-losses["r_multiple"].sum())

    if gross_loss > 0:
        pf = gross_win / gross_loss
    elif gross_win > 0:
        pf = float("inf")
    else:
        pf = 0.0

    base.update({
        "total_trades": int(len(df)),
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate": float(len(wins) / len(df)),
        "avg_win_r": float(wins["r_multiple"].mean()) if len(wins) else 0.0,
        "avg_loss_r": float(losses["r_multiple"].mean()) if len(losses) else 0.0,
        "expectancy_r": float(df["r_multiple"].mean()),
        "profit_factor": pf,
        "total_r": float(df["r_multiple"].sum()),
        "max_drawdown_r": _max_drawdown_r(df["r_multiple"]),
        "longest_losing_streak": _longest_losing_streak(df["r_multiple"]),
        "avg_bars_held": float(df["bars_held"].mean()),
        "avg_slippage_bps": float(df["slippage_bps"].mean()) if "slippage_bps" in df else 0.0,
    })
    return base


def breakdown(trades_df: pd.DataFrame, by: str) -> pd.DataFrame:
    if trades_df is None or trades_df.empty or by not in trades_df.columns:
        return pd.DataFrame()
    g = trades_df.groupby(by)
    out = pd.DataFrame({
        "trades": g.size(),
        "win_rate": g["r_multiple"].apply(lambda s: float((s > 0).mean())),
        "expectancy_r": g["r_multiple"].mean(),
        "total_r": g["r_multiple"].sum(),
        "avg_bars_held": g["bars_held"].mean(),
    })
    return out.sort_values("total_r", ascending=False)


def spread_buckets(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df is None or trades_df.empty:
        return pd.DataFrame()
    df = trades_df.copy()
    df["spread_bucket"] = pd.cut(
        df["spread_at_entry"],
        bins=[-0.0001, 0.001, 0.003, 0.005, 1.0],
        labels=["<0.1%", "0.1-0.3%", "0.3-0.5%", ">0.5%"],
    )
    return breakdown(df, "spread_bucket")
