"""
Backtest Engine - רץ את שרשרת הפילטרים על נתונים היסטוריים
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import config
from agents.screener_agent import compute_rsi, compute_atr
from utils import load_universe


def get_historical_data(tickers: list, start: str, end: str) -> dict:
    """מוריד נתונים יומיים לכל הטיקרים + SPY"""
    print(f"מוריד נתונים היסטוריים מ-{start} עד {end}...")
    data = {}
    
    # SPY לבנצ'מרק
    spy = yf.download("SPY", start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    data["SPY"] = spy

    for i, ticker in enumerate(tickers):
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if len(df) > 50:  # מספיק היסטוריה
                data[ticker] = df
        except Exception:
            pass
        if (i + 1) % 20 == 0:
            print(f"  הורדו {i+1}/{len(tickers)} טיקרים...")
    
    print(f"נטענו בהצלחה {len(data)-1} מניות + SPY")
    return data


def screen_on_date(ticker: str, df: pd.DataFrame, date, spy_df: pd.DataFrame) -> dict | None:
    """מריץ את אותם פילטרים של ה-Screener על תאריך ספציפי"""
    if date not in df.index:
        return None

    # לוקחים היסטוריה עד התאריך (כולל)
    hist = df.loc[:date].copy()
    if len(hist) < config.EMA_SLOW + 5:
        return None

    hist["EMA_fast"] = hist["Close"].ewm(span=config.EMA_FAST).mean()
    hist["EMA_slow"] = hist["Close"].ewm(span=config.EMA_SLOW).mean()
    hist["EMA_trend"] = hist["Close"].ewm(span=config.EMA_TREND).mean()
    hist["RSI"] = compute_rsi(hist["Close"], config.RSI_PERIOD)
    hist["ATR"] = compute_atr(hist, config.ATR_PERIOD)
    hist["vol_avg"] = hist["Volume"].rolling(20).mean()

    last = hist.iloc[-1]
    prev = hist.iloc[-2]

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

    # Relative Strength מול SPY
    if date in spy_df.index:
        spy_hist = spy_df.loc[:date]
        if len(spy_hist) >= 2:
            spy_change = (float(spy_hist["Close"].iloc[-1]) - float(spy_hist["Close"].iloc[-2])) / float(spy_hist["Close"].iloc[-2])
        else:
            spy_change = 0
    else:
        spy_change = 0

    stock_change = (price - prev_close) / prev_close if prev_close else 0
    relative_strength = stock_change - spy_change

    # --- פילטרים (זהים למערכת החיה) ---
    if not (config.PRICE_MIN <= price <= config.PRICE_MAX):
        return None
    if dollar_volume < config.MIN_DOLLAR_VOLUME:
        return None
    if config.GAP_REQUIRE_POSITIVE:
        if not (config.GAP_MIN_PCT <= gap_pct <= config.GAP_MAX_PCT):
            return None
    else:
        if not (config.GAP_MIN_PCT <= abs(gap_pct) <= config.GAP_MAX_PCT):
            return None
    if not ema_breakout or not above_ema_trend:
        return None
    if rsi is None or not (config.RSI_MIN <= rsi <= config.RSI_MAX):
        return None
    if rvol < config.RVOL_THRESHOLD:
        return None
    if atr_pct is None or not (config.ATR_MIN_PCT <= atr_pct <= config.ATR_MAX_PCT):
        return None
    if relative_strength < config.RS_MIN_OUTPERFORMANCE:
        return None

    # --- Catalyst Proxy (Gap חזק + RVOL גבוה) ---
    # במקום חדשות אמיתיות
    catalyst_score = 0
    if gap_pct >= 0.08:
        catalyst_score += 1
    if rvol >= 4.0:
        catalyst_score += 1
    if relative_strength >= 0.04:
        catalyst_score += 1

    if catalyst_score < 2:  # דורשים לפחות 2 מתוך 3
        return None

    return {
        "ticker": ticker,
        "date": date,
        "price": round(price, 2),
        "rsi": round(rsi, 1),
        "rvol": round(rvol, 2),
        "gap_pct": round(gap_pct * 100, 2),
        "relative_strength_pct": round(relative_strength * 100, 2),
        "atr_pct": round(atr_pct * 100, 2),
    }


def simulate_trade(candidate: dict, df: pd.DataFrame) -> dict | None:
    """מדמה כניסה ויציאה לפי Stop / Take Profit"""
    entry_date = candidate["date"]
    entry_price = candidate["price"]

    stop_loss = round(entry_price * (1 - config.STOP_LOSS_PCT), 2)
    take_profit = round(entry_price * (1 + config.TAKE_PROFIT_MIN_PCT), 2)  # משתמשים ב-MIN כברירת מחדל

    # Position sizing מבוסס סיכון
    risk_per_share = entry_price - stop_loss
    if risk_per_share <= 0:
        return None

    qty = int(config.RISK_PER_TRADE_DOLLARS // risk_per_share)
    max_qty = int((config.TOTAL_BUDGET * config.MAX_POSITION_VALUE_PCT) // entry_price)
    qty = min(qty, max_qty)
    if qty < 1:
        return None

    # מחפשים יציאה בימים הבאים (עד 5 ימי מסחר)
    future = df.loc[entry_date:].iloc[1:6]  # מדלגים על יום הכניסה

    exit_price = None
    exit_date = None
    exit_reason = None
    days_held = 0

    for i, (dt, row) in enumerate(future.iterrows()):
        days_held = i + 1
        high = float(row["High"])
        low = float(row["Low"])
        close = float(row["Close"])

        # בודקים אם נגענו ב-Stop או ב-TP במהלך היום
        if low <= stop_loss:
            exit_price = stop_loss
            exit_date = dt
            exit_reason = "stop_loss"
            break
        if high >= take_profit:
            exit_price = take_profit
            exit_date = dt
            exit_reason = "take_profit"
            break

        # אם הגענו ליום האחרון בלי לפגוע → יוצאים בסגירה
        if i == len(future) - 1:
            exit_price = close
            exit_date = dt
            exit_reason = "time_exit"

    if exit_price is None:
        return None

    # חישוב רווח/הפסד נטו (עמלות + מס)
    commission = config.COMMISSION_PER_TRADE * 2
    gross_pnl = qty * (exit_price - entry_price)
    net_before_tax = gross_pnl - commission

    if net_before_tax > 0:
        tax = net_before_tax * config.CAPITAL_GAINS_TAX_RATE
        net_pnl = net_before_tax - tax
    else:
        net_pnl = net_before_tax

    risk_dollars = qty * risk_per_share
    realized_rr = net_pnl / risk_dollars if risk_dollars > 0 else 0

    return {
        "ticker": candidate["ticker"],
        "entry_date": entry_date.strftime("%Y-%m-%d"),
        "exit_date": exit_date.strftime("%Y-%m-%d"),
        "entry_price": entry_price,
        "exit_price": round(exit_price, 2),
        "qty": qty,
        "days_held": days_held,
        "exit_reason": exit_reason,
        "gross_pnl": round(gross_pnl, 2),
        "net_pnl": round(net_pnl, 2),
        "risk_dollars": round(risk_dollars, 2),
        "realized_rr": round(realized_rr, 2),
    }


def run_backtest(start_date: str, end_date: str):
    universe = load_universe()
    data = get_historical_data(universe, start_date, end_date)

    if "SPY" not in data:
        print("שגיאה: לא הצלחנו להוריד את SPY")
        return []

    spy_df = data["SPY"]
    all_dates = spy_df.index.tolist()

    # נריץ רק על ימים שיש בהם מספיק היסטוריה
    trades = []
    print("\nמתחיל לסרוק ימים...")

    for i, date in enumerate(all_dates):
        if i < 30:  # מדלגים על החודש הראשון (צריך היסטוריה לאינדיקטורים)
            continue

        daily_candidates = []
        for ticker, df in data.items():
            if ticker == "SPY":
                continue
            candidate = screen_on_date(ticker, df, date, spy_df)
            if candidate:
                daily_candidates.append(candidate)

        # מדמים עסקאות
        for cand in daily_candidates:
            trade = simulate_trade(cand, data[cand["ticker"]])
            if trade:
                trades.append(trade)
                print(f"  {trade['entry_date']} | {trade['ticker']} | {trade['exit_reason']} | PnL: ${trade['net_pnl']}")

        if (i + 1) % 20 == 0:
            print(f"  עובד... נסרקו {i+1} ימים, נמצאו {len(trades)} עסקאות עד כה")

    return trades
