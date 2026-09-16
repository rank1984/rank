import pandas as pd
import os
import config

def load_universe() -> list:
    """טוען יקום מניות מ-CSV אם קיים, אחרת משתמש ב-config.UNIVERSE"""
    if os.path.exists(config.UNIVERSE_FILE):
        try:
            df = pd.read_csv(config.UNIVERSE_FILE)
            tickers = df["ticker"].dropna().astype(str).str.upper().str.strip().unique().tolist()
            print(f"נטענו {len(tickers)} טיקרים מ-{config.UNIVERSE_FILE}")
            return tickers
        except Exception as e:
            print(f"שגיאה בטעינת {config.UNIVERSE_FILE}: {e}. משתמש ב-UNIVERSE ברירת מחדל.")
            return config.UNIVERSE
    return config.UNIVERSE
