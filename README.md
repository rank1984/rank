# מערכת מרובת-סוכנים לאיתור מניות מומנטום (1-3 ימי החזקה)

מערכת מבוססת 3 סוכנים, כל אחד עם תפקיד ברור:

1. **Screener Agent** - סינון טכני: מחיר 5-30$, dollar volume>10M$, float 10M-150M,
   market cap 50M-2B, gap 5%-25%, EMA breakout, RSI 55-70, RVOL>3, ATR בטווח סביר,
   ו-Relative Strength מול SPY (המניה חייבת "לנצח" את המדד).
2. **Catalyst Agent** - שולף חדשות 24 שעות מ-Finnhub, מדרג קטליזטור A/B/C/D
   דרך LLM (Gemini/Groq) בקריאה אחת מרוכזת לכל המועמדים (חוסך API calls).
3. **Risk & Yield Manager** - דוחה קטליזטור מתחת ל-B, מחשב position sizing
   **מבוסס-סיכון בדולרים** (לא % מהתקציב), עמלות + מס רווחי הון 25%,
   ומוודא יחס סיכון:סיכוי נטו >= 1:3.

## למה Position Sizing מבוסס-סיכון?

במקום "תשקיע 20% מהתקציב במניה", המערכת שואלת "כמה דולרים מוכן להפסיד בעסקה
בודדת?" (ברירת מחדל: 2% מ-1000$ = 20$), ומחשבת כמות מניות מזה:

```
qty = risk_dollars / (entry_price - stop_loss_price)
```

זו הדרך המקצועית לנהל סיכון - היא לא תלויה במחיר המניה, אלא בגודל התנועה
שאתה מוכן לספוג.

## הקמה מהירה

```bash
git clone <your-repo-url>
cd momentum_mas
pip install -r requirements.txt
cp .env.example .env
# ערוך את .env
python orchestrator.py
```

## מפתחות API (כולם עם tier חינמי)

| שירות | למה | קישור |
|---|---|---|
| Gemini **או** Groq | סיווג קטליזטורים | aistudio.google.com / console.groq.com |
| Finnhub | חדשות | finnhub.io |
| Telegram Bot | התראות | @BotFather בטלגרם |

## הערה חשובה - VWAP

המערכת משתמשת ב-EMA20 יומי כתחליף ל"מגמה חיובית", **לא** VWAP אמיתי
(שהוא אינטרה-דיי). לחישוב VWAP אמיתי צריך מקור נתונים תוך-יומי נפרד.

## לפני כסף אמיתי

הרץ 2-3 שבועות על paper trading, בדוק את `logs/decisions.csv`, ורק אז שקול
מעבר לחשבון live. זה כלי מחקר/אוטומציה - לא ייעוץ השקעות.
