"""
בדיקת יקום (לתחזוקה חודשית, דורש רשת): נתונים, נר אחרון, מחיר, mcap, float, וסימון בעיות.
    python scripts/check_universe.py            -> logs/universe_check.csv
"""
import csv
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402

import config  # noqa: E402
from agents.screener_agent import fetch_market_info  # noqa: E402
from utils import load_universe  # noqa: E402


def main():
    rows = []
    for t in load_universe():
        flags = []
        last_date = price = dvol = None
        mc = fl = None
        try:
            tk = yf.Ticker(t)
            df = tk.history(period="1mo")
            if df is None or df.empty:
                flags.append("no_data")
            else:
                last_date = pd.Timestamp(df.index[-1]).date()
                price = float(df["Close"].iloc[-1])
                dvol = float((df["Close"] * df["Volume"]).tail(20).mean())
                if (datetime.now().date() - last_date).days > 7:
                    flags.append("stale")
                if not (config.PRICE_MIN <= price <= config.PRICE_MAX):
                    flags.append("price_out")
                if dvol < config.MIN_DOLLAR_VOLUME:
                    flags.append("dollar_volume_low")
            mc, fl, _ = fetch_market_info(tk)
            if mc is None or fl is None:
                flags.append("missing_mcap_or_float")
            else:
                if not (config.MARKET_CAP_MIN <= mc <= config.MARKET_CAP_MAX):
                    flags.append("mcap_out")
                if not (config.FLOAT_MIN <= fl <= config.FLOAT_MAX):
                    flags.append("float_out")
        except Exception as e:  # noqa: BLE001
            flags.append(f"error:{e}")
        rows.append({"ticker": t, "last_bar": last_date, "price": price, "avg_dollar_vol_m": None if dvol is None else round(dvol / 1e6, 1),
                     "market_cap_m": None if mc is None else round(mc / 1e6), "float_m": None if fl is None else round(fl / 1e6),
                     "flags": ";".join(flags)})
        print(f"{t:<8} {last_date} {price if price is None else round(price, 2)} {';'.join(flags) or 'ok'}")

    os.makedirs("logs", exist_ok=True)
    with open("logs/universe_check.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    ok = [r["ticker"] for r in rows if not r["flags"]]
    print(f"\nתקינים (עוברים את כל בדיקות היקום): {len(ok)}/{len(rows)}")
    print("טיקרים שהוחלפו/הופסקו (SQ->XYZ, PARA->PSKY, NKLA, RIDE, GOEV, FFIE, MULN...) יופיעו כ-no_data/stale. לאמת ידנית.")


if __name__ == "__main__":
    main()
