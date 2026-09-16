"""
VWAP Reclaim / ORB setup — חישוב אותות וניהול רמות.
כל החישובים כאן הם backward-looking בלבד.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class SetupConfig:
    rvol_min: float = 2.5
    rvol_strong: float = 3.0
    rsi_min: float = 50.0
    rsi_max_base: float = 75.0
    rsi_max_strong: float = 85.0
    max_spread_pct: float = 0.005
    min_price: float = 2.0
    or_minutes: int = 15
    stop_buffer_pct: float = 0.002
    target_r: float = 2.0
    min_rr: float = 1.5
    rsi_period: int = 14
    rvol_lookback_days: int = 10


def _session(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["session"] = df["timestamp"].dt.date
    return df


def _running_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    VWAP מתגלגל מסה פתיחה — לא VWAP של יום שלם.
    זה קריטי: VWAP יומי מלא הוא Look-ahead.
    """
    df = df.copy()
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = tp * df["volume"]
    df["cum_pv"] = pv.groupby(df["session"]).cumsum()
    df["cum_v"] = df["volume"].groupby(df["session"]).cumsum()
    df["vwap"] = df["cum_pv"] / df["cum_v"].replace(0, np.nan)
    return df


def _rvol(df: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    """
    RVOL לפי slot של שעה — נפח הנר מול ממוצע N ימים קודמים לאותו slot.
    ה-shift(1) מבטיח שהיום הנוכחי לא נכלל בממוצע.
    """
    df = df.copy()
    df["slot"] = df["timestamp"].dt.strftime("%H:%M")

    daily = df.groupby(["session", "slot"], as_index=False)["volume"].sum()
    daily["avg_vol_slot"] = (
        daily.groupby("slot")["volume"]
        .transform(lambda s: s.shift(1).rolling(lookback_days, min_periods=1).mean())
    )
    df = df.merge(daily[["session", "slot", "avg_vol_slot"]],
                  on=["session", "slot"], how="left")
    df["rvol"] = df["volume"] / df["avg_vol_slot"].replace(0, np.nan)
    return df


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = (-delta).clip(lower=0)
    roll_up = up.ewm(alpha=1 / period, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _opening_range(df: pd.DataFrame, or_minutes: int) -> pd.DataFrame:
    df = df.copy()
    session_open = df.groupby("session")["timestamp"].transform("min")
    df["minutes_from_open"] = (
        (df["timestamp"] - session_open).dt.total_seconds() / 60.0
    )
    in_or = df["minutes_from_open"] < or_minutes

    or_high = df[in_or].groupby("session")["high"].max()
    or_low = df[in_or].groupby("session")["low"].min()

    df["or_high"] = df["session"].map(or_high)
    df["or_low"] = df["session"].map(or_low)
    df["in_or"] = in_or
    return df


def prepare_features(df: pd.DataFrame, cfg: SetupConfig) -> pd.DataFrame:
    """
    נקודת הכניסה היחידה. מחזיר df מוכן לאיתות.
    דורש עמודות: timestamp, open, high, low, close, volume.
    אופציונלי: spread_pct, symbol.
    """
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.copy().sort_values("timestamp").reset_index(drop=True)
    df = _session(df)
    df = _running_vwap(df)
    df = _rvol(df, lookback_days=cfg.rvol_lookback_days)
    df["rsi"] = df.groupby("session")["close"].transform(
        lambda s: _rsi(s, period=cfg.rsi_period)
    )
    df = _opening_range(df, or_minutes=cfg.or_minutes)

    if "spread_pct" not in df.columns:
        df["spread_pct"] = 0.0
    if "symbol" not in df.columns:
        df["symbol"] = "UNKNOWN"
    return df


def generate_signals(df: pd.DataFrame, cfg: SetupConfig) -> pd.DataFrame:
    """
    מייצר עמודת signal בוליאנית. האות מחושב לפי נתוני הנר t בלבד.
    הכניסה תתבצע בנר t+1 — מנוהל ב-run_intraday.
    """
    df = df.copy()
    prev_close = df["close"].shift(1)
    prev_vwap = df["vwap"].shift(1)

    reclaim = (df["close"] > df["vwap"]) & (prev_close <= prev_vwap)
    after_or = ~df["in_or"]

    rvol_ok = df["rvol"] >= cfg.rvol_min
    rsi_normal = (df["rsi"] >= cfg.rsi_min) & (df["rsi"] <= cfg.rsi_max_base)
    rsi_strong = (df["rvol"] >= cfg.rvol_strong) & (df["rsi"] <= cfg.rsi_max_strong)
    rsi_ok = rsi_normal | rsi_strong

    spread_ok = df["spread_pct"] <= cfg.max_spread_pct
    price_ok = df["close"] >= cfg.min_price

    df["signal"] = (
        reclaim & after_or & rvol_ok & rsi_ok & spread_ok & price_ok
    )
    return df


def compute_stop_level(signal_bar: pd.Series, cfg: SetupConfig) -> Optional[float]:
    """
    קובע את מחיר הסטופ ביום האיתות.
    רמת הסטופ קפואה — לא משתנה עם הכניסה בפועל.
    """
    close = float(signal_bar["close"])
    vwap = signal_bar.get("vwap")
    or_low = signal_bar.get("or_low")

    candidates = [
        float(x) for x in (vwap, or_low)
        if x is not None and not pd.isna(x) and float(x) < close
    ]
    if not candidates:
        return None
    return max(candidates) * (1.0 - cfg.stop_buffer_pct)
