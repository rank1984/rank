import pandas as pd
import os
import config
from datetime import datetime, timedelta

def expected_session_date(dt: datetime = None) -> datetime.date:
    """
    מחזיר את תאריך יום המסחר הצפוי.
    אם היום יום שבת או ראשון, מחזיר את יום שישי האחרון.
    """
    if dt is None:
        dt = datetime.now()
    
    # 5 = שבת, 6 = ראשון (בספירה של Python שמתחילה מ-0 ביום שני)
    if dt.weekday() == 5:
        return (dt - timedelta(days=1)).date()
    elif dt.weekday() == 6:
        return (dt - timedelta(days=2)).date()
    
    return dt.date()

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
