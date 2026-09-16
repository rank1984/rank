"""
סוכן 1: Screener Agent
סורק את יקום המניות ומוצא מועמדות עם מומנטום טכני אמיתי + עוצמה יחסית מול השוק
פילטרים: מחיר, dollar volume, float, market cap, gap%, EMA breakout,
RSI, RVOL, ATR, ו-Relative Strength מול SPY/QQQ
"""

import yfinance as yf
import pandas as pd
import config


def compute_rsi(series, period=14):
    """RSI לפי Wilder's smoothing (EMA) – השיטה המקורית והמדויקת יותר"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    # Wilder's smoothing = Exponential Moving Average עם alpha = 1/period
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_atr(df, period=14):
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def get_benchmark_change() -> float:
    """מחזיר את השינוי היומי (%) של מדד הייחוס (SPY/QQQ) - לצורך Relative Strength"""
    df = yf.download(config.RS_BENCHMARK, period="5d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty or len(df) < 2:
        return 0.0
    last_close = float(df["Close"].iloc[-1])
    prev_close = float(df["Close"].iloc[-2])
    return (last_close - prev_close) / prev_close


def screen_ticker(ticker: str, benchmark_change: float) -> dict | None:
    """מחזיר dict עם נתוני המועמדות אם עברה את כל הפילטרים, אחרת None"""
    tk = yf.Ticker(ticker)
    df = tk.history(period="3mo")
    if df.empty or len(df) < config.EMA_SLOW + 5:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    try:
        info = tk.info
        market_cap = info.get("marketCap")
        float_shares = info.get("floatShares")
    except Exception:
        market_cap, float_shares = None, None

    df["EMA_fast"] = df["Close"].ewm(span=config.EMA_FAST).mean()
    df["EMA_slow"] = df["Close"].ewm(span=config.EMA_SLOW).mean()
    df["EMA_trend"] = df["Close"].ewm(span=config.EMA_TREND).mean()
    df["RSI"] = compute_rsi(df["Close"], config.RSI_PERIOD)
    df["ATR"] = compute_atr(df, config.ATR_PERIOD)
    df["vol_avg"] = df["Volume"].rolling(20).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(last["Close"])
    prev_close = float(prev["Close"])
    open_price = float(last["Open"])
    avg_vol = float(last["vol_avg"]) if not pd.isna(last["vol_avg"]) else 0
    rsi = float(last["RSI"]) if not pd.isna(last["RSI"]) else None
    atr = float(last["ATR"]) if not pd.isna(last["ATR"]) else None
    atr_pct = (atr / price) if (atr and price) else None
    rvol = float(last["Volume"] / avg_vol) if avg_vol > 0 else 0
    dollar_volume = price * avg_vol
    ema_breakout = last["EMA_fast"] > last["EMA_slow"]
    above_ema_trend = price > float(last["EMA_trend"])
    gap_pct = (open_price - prev_close) / prev_close if prev_close else 0

    stock_change = (price - prev_close) / prev_close if prev_close else 0
    relative_strength = stock_change - benchmark_change

    reject_reason = None
    if not (config.PRICE_MIN <= price <= config.PRICE_MAX):
        reject_reason = "price_out_of_range"
    elif dollar_volume < config.MIN_DOLLAR_VOLUME:
        reject_reason = "dollar_volume_too_low"
    elif market_cap and not (config.MARKET_CAP_MIN <= market_cap <= config.MARKET_CAP_MAX):
        reject_reason = "market_cap_out_of_range"
    elif float_shares and not (config.FLOAT_MIN <= float_shares <= config.FLOAT_MAX):
        reject_reason = "float_out_of_range"
    elif config.GAP_REQUIRE_POSITIVE:
        if not (config.GAP_MIN_PCT <= gap_pct <= config.GAP_MAX_PCT):
            reject_reason = "gap_out_of_range"
    elif not (config.GAP_MIN_PCT <= abs(gap_pct) <= config.GAP_MAX_PCT):
        reject_reason = "gap_out_of_range"
    elif not ema_breakout:
        reject_reason = "no_ema_breakout"
    elif not above_ema_trend:
        reject_reason = "below_ema_trend"
    elif rsi is None or not (config.RSI_MIN <= rsi <= config.RSI_MAX):
        reject_reason = "rsi_out_of_range"
    elif rvol < config.RVOL_THRESHOLD:
        reject_reason = "rvol_too_low"
    elif atr_pct is None or not (config.ATR_MIN_PCT <= atr_pct <= config.ATR_MAX_PCT):
        reject_reason = "atr_out_of_range"
    elif relative_strength < config.RS_MIN_OUTPERFORMANCE:
        reject_reason = "weak_relative_strength"

    if reject_reason:
        return None

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "rsi": round(rsi, 1),
        "rvol": round(rvol, 2),
        "atr_pct": round(atr_pct * 100, 2),
        "dollar_volume_m": round(dollar_volume / 1_000_000, 1),
        "market_cap_m": round(market_cap / 1_000_000, 1) if market_cap else None,
        "float_m": round(float_shares / 1_000_000, 1) if float_shares else None,
        "gap_pct": round(gap_pct * 100, 2),
        "relative_strength_pct": round(relative_strength * 100, 2),
        "benchmark_change_pct": round(benchmark_change * 100, 2),
    }


def run_screener(universe: list) -> list:
    """מריץ סינון על כל היקום, מחזיר רשימת מועמדות שעברו את כל הפילטרים"""
    print(f"  שולף שינוי יומי של {config.RS_BENCHMARK} (בנצ'מרק ל-Relative Strength)...")
    benchmark_change = get_benchmark_change()
    print(f"  {config.RS_BENCHMARK}: {benchmark_change*100:.2f}%")

    candidates = []
    for ticker in universe:
        try:
            result = screen_ticker(ticker, benchmark_change)
            if result:
                candidates.append(result)
                print(
                    f"  ✓ {ticker}: RSI={result['rsi']} RVOL={result['rvol']} "
                    f"RS={result['relative_strength_pct']}% $Vol={result['dollar_volume_m']}M"
                )
        except Exception as e:
            print(f"  ✗ {ticker}: שגיאה - {e}")
    return candidates
