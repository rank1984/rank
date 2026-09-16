"""
כל הפרמטרים של המערכת - כאן מכוונים את ההתנהגות בלי לגעת בלוגיקה
"""

# --- יקום מניות לסריקה ---
# רשימת התחלה - הרחב לפי הצורך (אפשר לטעון מ-CSV של S&P/Russell בעתיד)
UNIVERSE = [
    "SIRI", "SOFI", "PLUG", "F", "NOK", "RIOT", "MARA", "CHPT",
    "LCID", "NIO", "PLTR", "AAL", "CCL", "WBD", "PARA", "VALE",
]

PRICE_MIN = 5.0
PRICE_MAX = 30.0
MIN_AVG_VOLUME = 500_000          # פילטר בסיסי לפני dollar volume
MIN_DOLLAR_VOLUME = 10_000_000    # מחזור x מחיר - הפילטר האמיתי לנזילות

# --- פילטרי Market Cap / Float (מסננים lottery-tickets מסוכנים מדי) ---
MARKET_CAP_MIN = 50_000_000
MARKET_CAP_MAX = 2_000_000_000
FLOAT_MIN = 10_000_000
FLOAT_MAX = 150_000_000

# --- Gap Filter (פער בין פתיחה לסגירה קודמת) ---
GAP_MIN_PCT = 0.05
GAP_MAX_PCT = 0.25

# --- סוכן טכני (Screener Agent) ---
EMA_FAST = 9
EMA_SLOW = 21
EMA_TREND = 20                 # לבדיקת "מחיר מעל EMA20" כתחליף ל-VWAP יומי
RSI_PERIOD = 14
RSI_MIN = 55
RSI_MAX = 70
RVOL_THRESHOLD = 3.0           # נפח יחסי מינימלי (הועלה מ-2 ל-3 לפי ההמלצה)
ATR_PERIOD = 14
ATR_MIN_PCT = 0.02             # תנודתיות מינימלית (2% מהמחיר) - מסנן "רעש שקט"
ATR_MAX_PCT = 0.15             # תנודתיות מקסימלית - מסנן כאוס קיצוני

# --- Relative Strength (עוצמה מול השוק) ---
RS_BENCHMARK = "SPY"           # אפשר גם QQQ
RS_MIN_OUTPERFORMANCE = 0.02   # המניה חייבת "לנצח" את המדד ב-2% לפחות באותו יום

# הערה חשובה: VWAP אמיתי הוא אינטרה-דיי. במערכת שרצה על נתוני סגירה יומיים
# (yfinance daily), EMA20 משמש כתחליף סביר ל"מגמה חיובית", לא VWAP אמיתי.
# לחישוב VWAP אמיתי צריך מקור נתונים אינטרה-דיי נפרד (למשל Polygon/Finnhub tick data).

# --- סוכן חדשות (Catalyst Agent) - דירוג A/B/C/D ---
LLM_PROVIDER = "gemini"        # "gemini" או "groq"
GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"
NEWS_LOOKBACK_HOURS = 24
REQUIRE_NEWS = True             # אם True: מניה בלי חדשות כלל נפסלת אוטומטית

# דירוג קטליזטורים - A/B הכי חזקים, C חלש, D=אין חדשות
CATALYST_TIER_MIN_ACCEPTABLE = "B"   # רק A או B יאושרו סופית (ראה catalyst_agent)

CATALYST_KEYWORDS_TIER_A = [
    "fda approval", "fda clearance", "earnings beat", "raises guidance",
    "major contract", "acquisition", "merger", "buyout", "patent granted",
]
CATALYST_KEYWORDS_TIER_B = [
    "partnership", "collaboration", "new product launch", "analyst upgrade",
    "price target raised", "expands", "strategic",
]
CATALYST_KEYWORDS_TIER_C = [
    "press release", "announces", "update", "conference", "webinar",
]

# --- סוכן סיכונים (Risk & Yield Manager) ---
HOLDING_DAYS_MIN = 1
HOLDING_DAYS_MAX = 3
STOP_LOSS_PCT = 0.04             # -4% סטופ-לוס (ברירת מחדל, ה-qty נגזר מהסיכון בדולר)
TAKE_PROFIT_MIN_PCT = 0.10       # יעד רווח מינימלי - טווח 10%-30% לפי ההמלצה
TAKE_PROFIT_MAX_PCT = 0.30
MIN_RISK_REWARD = 3.0            # יחס סיכון:סיכוי מינימלי לאישור עסקה

TOTAL_BUDGET = 1000

# --- Position Sizing מבוסס-סיכון (השדרוג המרכזי) ---
# במקום "% מהתקציב", קובעים כמה דולרים מוכנים לאבד בעסקה בודדת,
# וגודל הפוזיציה נגזר מזה: qty = RISK_PER_TRADE_DOLLARS / (entry - stop)
RISK_PER_TRADE_PCT = 0.02        # 2% מהחשבון בסיכון לעסקה
RISK_PER_TRADE_DOLLARS = TOTAL_BUDGET * RISK_PER_TRADE_PCT  # = $20 על חשבון של $1000
MAX_POSITION_VALUE_PCT = 0.35    # תקרה נוספת: לא יותר מ-35% מהתקציב בפוזיציה אחת
MAX_OPEN_POSITIONS = 3

# עמלות ברוקר ישראלי - עדכן לפי הברוקר שלך
COMMISSION_PER_TRADE = 3.0       # $ לעסקה (קנייה או מכירה בנפרד)
CAPITAL_GAINS_TAX_RATE = 0.25    # מס רווחי הון בישראל

# --- טלגרם ---
LOG_FILE = "logs/decisions.csv"
