"""
מנוע Backtest Intraday ל-VWAP Reclaim.
כניסה בפתיחת הנר העוקב לאות בלבד. אין שימוש במידע עתידי.
"""
import argparse
from pathlib import Path

import pandas as pd

from backtest.setups import (
    SetupConfig, prepare_features, generate_signals, compute_stop_level,
)
from backtest.slippage import SCENARIOS, SlippageModel
from backtest.metrics import calculate_metrics, breakdown, spread_buckets


def simulate_trade(
    df: pd.DataFrame,
    signal_pos: int,
    cfg: SetupConfig,
    slippage: SlippageModel,
    catalyst_type: str = "none",
) -> dict | None:
    """
    מדמה עסקה אחת. signal_pos הוא אינדקס positional של נר האות.
    כניסה: open של signal_pos + 1, באותו סשן בלבד.
    """
    signal_bar = df.iloc[signal_pos]
    if signal_pos + 1 >= len(df):
        return None
    entry_bar = df.iloc[signal_pos + 1]
    if entry_bar["session"] != signal_bar["session"]:
        return None

    stop_level = compute_stop_level(signal_bar, cfg)
    if stop_level is None:
        return None

    spread_pct = float(signal_bar.get("spread_pct", 0.0) or 0.0)
    bar_range_pct = float(
        (signal_bar["high"] - signal_bar["low"]) / max(signal_bar["close"], 1e-9)
    )

    raw_entry = float(entry_bar["open"])
    entry = slippage.apply_entry(raw_entry, spread_pct, bar_range_pct)

    risk = entry - stop_level
    if risk <= 0:
        return None
    target = entry + cfg.target_r * risk

    exit_price: float | None = None
    exit_reason: str | None = None
    exit_pos: int | None = None

    for j in range(signal_pos + 1, len(df)):
        bar = df.iloc[j]
        if bar["session"] != signal_bar["session"]:
            break

        # שמרני: stop נבדק לפני target בתוך אותו נר
        if bar["low"] <= stop_level:
            fill = min(float(bar["open"]), stop_level)
            exit_price = slippage.apply_exit(fill, spread_pct, bar_range_pct)
            exit_reason = "stop"
            exit_pos = j
            break
        if bar["high"] >= target:
            fill = max(float(bar["open"]), target)
            exit_price = slippage.apply_exit(fill, spread_pct, bar_range_pct)
            exit_reason = "target"
            exit_pos = j
            break

    if exit_price is None:
        # יציאה בסוף הסשן
        last_pos = None
        for j in range(signal_pos + 1, len(df)):
            if df.iloc[j]["session"] != signal_bar["session"]:
                break
            last_pos = j
        if last_pos is None:
            return None
        exit_pos = last_pos
        exit_price = slippage.apply_exit(
            float(df.iloc[exit_pos]["close"]), spread_pct, bar_range_pct
        )
        exit_reason = "session_close"

    r_multiple = (exit_price - entry) / risk
    bars_held = exit_pos - (signal_pos + 1) + 1

    return {
        "symbol": signal_bar.get("symbol", "UNKNOWN"),
        "strategy": "VWAP_RECLAIM",
        "signal_ts": signal_bar["timestamp"],
        "entry_ts": entry_bar["timestamp"],
        "exit_ts": df.iloc[exit_pos]["timestamp"],
        "entry_price": entry,
        "raw_entry_price": raw_entry,
        "exit_price": exit_price,
        "stop": stop_level,
        "target": target,
        "risk_per_share": risk,
        "r_multiple": r_multiple,
        "pnl_per_share": exit_price - entry,
        "bars_held": bars_held,
        "exit_reason": exit_reason,
        "hour_of_day": int(signal_bar["timestamp"].hour),
        "spread_at_entry": spread_pct,
        "rvol_at_entry": float(signal_bar.get("rvol", 0.0) or 0.0),
        "rsi_at_entry": float(signal_bar.get("rsi", 0.0) or 0.0),
        "catalyst_type": catalyst_type,
        "slippage_bps": slippage.effective_bps(spread_pct, bar_range_pct),
    }


def run_backtest(
    df: pd.DataFrame,
    cfg: SetupConfig | None = None,
    scenarios: dict[str, SlippageModel] | None = None,
    catalyst_map: dict[str, str] | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    cfg = cfg or SetupConfig()
    scenarios = scenarios or SCENARIOS
    catalyst_map = catalyst_map or {}

    df = df.reset_index(drop=True).copy()
    df = prepare_features(df, cfg)
    df = generate_signals(df, cfg)

    signal_positions = df.index[df["signal"]].tolist()
    results: dict[str, pd.DataFrame] = {}

    for name, slip in scenarios.items():
        trades = []
        for pos in signal_positions:
            sym = df.iloc[pos].get("symbol", "UNKNOWN")
            catalyst_type = catalyst_map.get(sym, "none")
            trade = simulate_trade(df, pos, cfg, slip, catalyst_type=catalyst_type)
            if trade:
                trades.append(trade)
        results[name] = pd.DataFrame(trades)

    return results, df


def _fmt(v):
    if isinstance(v, float):
        if v == float("inf"):
            return "inf"
        return f"{v:.4f}"
    return str(v)


def print_summary(name: str, metrics: dict, trades_df: pd.DataFrame) -> None:
    print(f"\n=== Scenario: {name} ===")
    for k, v in metrics.items():
        print(f"  {k:24}: {_fmt(v)}")
    if trades_df.empty:
        return

    print("\n-- by hour_of_day --")
    print(breakdown(trades_df, "hour_of_day"))
    print("\n-- by exit_reason --")
    print(breakdown(trades_df, "exit_reason"))
    print("\n-- by catalyst_type --")
    print(breakdown(trades_df, "catalyst_type"))
    print("\n-- by spread bucket --")
    print(spread_buckets(trades_df))


def load_data(path: Path, symbol: str | None = None) -> pd.DataFrame:
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path, parse_dates=["timestamp"])
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    if "timestamp" not in df.columns:
        raise ValueError("Data must contain 'timestamp' column")
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    if symbol:
        if "symbol" not in df.columns:
            raise ValueError("--symbol given but no 'symbol' column in data")
        df = df[df["symbol"] == symbol].copy()

    if "symbol" not in df.columns:
        df["symbol"] = symbol or "UNKNOWN"

    return df.sort_values("timestamp").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Intraday VWAP Reclaim backtest")
    parser.add_argument("--data", required=True, help="parquet/csv with intraday bars")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--out", default="backtest/out")
    args = parser.parse_args()

    df = load_data(Path(args.data), symbol=args.symbol)
    results, _ = run_backtest(df)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, trades in results.items():
        metrics = calculate_metrics(trades)
        print_summary(name, metrics, trades)
        out_file = out_dir / f"trades_{name}.csv"
        trades.to_csv(out_file, index=False)
        print(f"\n[saved] {out_file}")


if __name__ == "__main__":
    main()
