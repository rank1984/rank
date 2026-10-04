"""
פילטרים טכניים - מקור אמת יחיד ל-live, backtest ו-count_signals.

evaluate_filters מחזיר רשימה של *כל* הפילטרים שנכשלו (לפי סדר קבוע), בלי שרשרת elif.
"""
import pandas as pd

import config

# סדר הבדיקות = סדר ה-reject_reason הראשון
CHECK_ORDER = [
    "price_out_of_range",
    "dollar_volume_too_low",
    "gap_out_of_range",
    "no_ema_breakout",
    "below_ema_trend",
    "rsi_out_of_range",
    "rvol_too_low",
    "atr_out_of_range",
    "weak_relative_strength",
    "missing_mcap_or_float",
    "market_cap_out_of_range",
    "float_out_of_range",
]


def compute_rsi(series, period=14):
    """RSI לפי Wilder's smoothing"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_atr(df, period=14):
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """מוסיף אינדיקטורים. כולם סיבתיים (ערך בנר t תלוי רק בנרות עד t)."""
    df = df.copy()
    df["EMA_fast"] = df["Close"].ewm(span=config.EMA_FAST).mean()
    df["EMA_slow"] = df["Close"].ewm(span=config.EMA_SLOW).mean()
    df["EMA_trend"] = df["Close"].ewm(span=config.EMA_TREND).mean()
    df["RSI"] = compute_rsi(df["Close"], config.RSI_PERIOD)
    df["ATR"] = compute_atr(df, config.ATR_PERIOD)
    df["vol_avg"] = df["Volume"].rolling(20).mean()
    return df


def bar_date_of(ts) -> "pd.Timestamp.date":
    return pd.Timestamp(ts).date()


def features_at(df: pd.DataFrame, pos: int, benchmark_change: float | None = None) -> dict | None:
    """
    פיצ'רים של הנר במיקום pos (df חייב להכיל אינדיקטורים).
    ערכים כשברים (gap 0.08 = 8%).
    """
    if pos < 1 or pos >= len(df):
        return None
    last = df.iloc[pos]
    prev = df.iloc[pos - 1]

    price = float(last["Close"])
    prev_close = float(prev["Close"])
    open_price = float(last["Open"])
    avg_vol = float(last["vol_avg"]) if not pd.isna(last["vol_avg"]) else 0.0
    rsi = float(last["RSI"]) if not pd.isna(last["RSI"]) else None
    atr = float(last["ATR"]) if not pd.isna(last["ATR"]) else None
    atr_pct = (atr / price) if (atr and price) else None
    rvol = float(last["Volume"] / avg_vol) if avg_vol > 0 else 0.0
    stock_change = (price - prev_close) / prev_close if prev_close else 0.0

    f = {
        "bar_date": bar_date_of(df.index[pos]),
        "price": price,
        "prev_close": prev_close,
        "open": open_price,
        "high": float(last["High"]),
        "low": float(last["Low"]),
        "volume": float(last["Volume"]),
        "rsi": rsi,
        "atr_pct": atr_pct,
        "rvol": rvol,
        "avg_vol": avg_vol,
        "dollar_volume": price * avg_vol,
        "ema_breakout": bool(last["EMA_fast"] > last["EMA_slow"]),
        "above_ema_trend": bool(price > float(last["EMA_trend"])),
        "gap_pct": ((open_price - prev_close) / prev_close) if prev_close else 0.0,
        "stock_change": stock_change,
        "relative_strength": None,
    }
    if benchmark_change is not None:
        f["relative_strength"] = stock_change - benchmark_change
    return f


def evaluate_filters(f: dict, market_cap=None, float_shares=None, check_mcap_float: bool = True) -> list:
    """מחזיר רשימת שמות הפילטרים שנכשלו (ריקה = עבר הכול)."""
    failed = []
    price = f["price"]
    gap = f["gap_pct"]
    rsi = f["rsi"]
    atr_pct = f["atr_pct"]
    rs = f.get("relative_strength")

    if config.GAP_REQUIRE_POSITIVE:
        gap_ok = config.GAP_MIN_PCT <= gap <= config.GAP_MAX_PCT
    else:
        gap_ok = config.GAP_MIN_PCT <= abs(gap) <= config.GAP_MAX_PCT

    checks = {
        "price_out_of_range": not (config.PRICE_MIN <= price <= config.PRICE_MAX),
        "dollar_volume_too_low": f["dollar_volume"] < config.MIN_DOLLAR_VOLUME,
        "gap_out_of_range": not gap_ok,
        "no_ema_breakout": not f["ema_breakout"],
        "below_ema_trend": not f["above_ema_trend"],
        "rsi_out_of_range": rsi is None or not (config.RSI_MIN <= rsi <= config.RSI_MAX),
        "rvol_too_low": f["rvol"] < config.RVOL_THRESHOLD,
        "atr_out_of_range": atr_pct is None or not (config.ATR_MIN_PCT <= atr_pct <= config.ATR_MAX_PCT),
        "weak_relative_strength": rs is None or rs < config.RS_MIN_OUTPERFORMANCE,
    }
    if check_mcap_float:
        checks["missing_mcap_or_float"] = bool(
            config.FAIL_CLOSED_MCAP_FLOAT and (market_cap is None or float_shares is None)
        )
        checks["market_cap_out_of_range"] = (
            market_cap is not None and not (config.MARKET_CAP_MIN <= market_cap <= config.MARKET_CAP_MAX)
        )
        checks["float_out_of_range"] = (
            float_shares is not None and not (config.FLOAT_MIN <= float_shares <= config.FLOAT_MAX)
        )

    for name in CHECK_ORDER:
        if checks.get(name):
            failed.append(name)
    return failed
