"""
סוכן 2: Catalyst Agent
שולף חדשות 24 שעות אחרונות מ-Finnhub עבור מועמדות שעברו סינון טכני,
ושולח ל-LLM (Gemini/Groq) בקריאה אחת מרוכזת (לא קריאה לכל טיקר!)
כדי לסווג האם יש קטליזטור פונדמנטלי אמיתי
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
import config


def fetch_news_finnhub(ticker: str, hours: int = 24) -> list:
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return []

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(hours=hours + 24)).strftime("%Y-%m-%d")

    url = "https://finnhub.io/api/v1/company-news"
    params = {"symbol": ticker, "from": from_date, "to": to_date, "token": api_key}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        articles = resp.json()
    except Exception as e:
        print(f"    שגיאת Finnhub עבור {ticker}: {e}")
        return []

    cutoff = datetime.now() - timedelta(hours=hours)
    recent = []
    for a in articles[:10]:  # מגביל ל-10 כותרות אחרונות לכל טיקר
        pub_time = datetime.fromtimestamp(a.get("datetime", 0))
        if pub_time >= cutoff:
            recent.append({"headline": a.get("headline", ""), "summary": a.get("summary", "")[:200]})
    return recent


def _call_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("no_gemini_key")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent?key={api_key}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(url, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_groq(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("no_groq_key")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    body = {
        "model": config.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _classify_tier_by_keywords(text: str) -> tuple[str, str]:
    """מסווג טקסט לדרגה A/B/C/D לפי מילות מפתח, מחזיר (tier, matched_keyword)"""
    text_lower = text.lower()
    for kw in config.CATALYST_KEYWORDS_TIER_A:
        if kw in text_lower:
            return "A", kw
    for kw in config.CATALYST_KEYWORDS_TIER_B:
        if kw in text_lower:
            return "B", kw
    for kw in config.CATALYST_KEYWORDS_TIER_C:
        if kw in text_lower:
            return "C", kw
    return "D", "none"


def _keyword_fallback(ticker_news: dict) -> dict:
    """סיווג A/B/C/D מבוסס מילות מפתח, אם ה-LLM לא זמין"""
    results = {}
    for ticker, articles in ticker_news.items():
        text = " ".join(a["headline"] + " " + a["summary"] for a in articles)
        tier, matched = _classify_tier_by_keywords(text)
        results[ticker] = {
            "catalyst_tier": tier,
            "catalyst_type": matched,
            "confidence": "low_keyword_based",
        }
    return results


def classify_catalysts(ticker_news: dict) -> dict:
    """
    מקבל dict {ticker: [articles]} ומחזיר dict {ticker: {has_catalyst, catalyst_type, confidence}}
    שולח קריאת LLM אחת מרוכזת לכל המועמדים יחד - חוסך קריאות API
    """
    # מסנן טיקרים בלי חדשות בכלל
    tickers_with_news = {t: arts for t, arts in ticker_news.items() if arts}
    if not tickers_with_news:
        return {t: {"catalyst_tier": "D", "catalyst_type": "no_news", "confidence": "n/a"} for t in ticker_news}

    prompt = (
        "אתה מנתח פיננסי. עבור כל מניה, דרג את חוזק הקטליזטור בחדשות לפי הסולם:\n"
        "A = חזק מאוד (אישור FDA, Earnings beat משמעותי, חוזה גדול, רכישה/מיזוג, פטנט)\n"
        "B = בינוני (שיתוף פעולה, מוצר חדש, שדרוג אנליסט, יעד מחיר מוגדל)\n"
        "C = חלש (הודעה לעיתונות כללית, כנס, עדכון שגרתי)\n"
        "D = אין קטליזטור אמיתי\n\n"
        "החזר JSON בלבד, בפורמט הבא, ללא טקסט נוסף:\n"
        '{"TICKER": {"catalyst_tier": "A/B/C/D", "catalyst_type": "תיאור קצר", "confidence": "high/medium/low"}}\n\n'
        "נתונים:\n"
    )
    for ticker, articles in tickers_with_news.items():
        prompt += f"\n{ticker}:\n"
        for a in articles[:5]:
            prompt += f"  - {a['headline']}\n"

    raw_response = None
    try:
        if config.LLM_PROVIDER == "gemini":
            raw_response = _call_gemini(prompt)
        else:
            raw_response = _call_groq(prompt)
    except Exception as e:
        print(f"    LLM נכשל ({e}), עובר ל-keyword fallback")
        return _keyword_fallback(ticker_news)

    # ניקוי ופרסור JSON (מודלים לפעמים עוטפים ב-```json)
    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            cleaned = cleaned.replace("json", "", 1).strip()
        parsed = json.loads(cleaned)
    except Exception as e:
        print(f"    שגיאת פרסור JSON מה-LLM ({e}), עובר ל-keyword fallback")
        return _keyword_fallback(ticker_news)

    # השלמת טיקרים שלא היו בתשובה (למשל אם לא היו להם חדשות)
    for t in ticker_news:
        if t not in parsed:
            parsed[t] = {"catalyst_tier": "D", "catalyst_type": "no_news", "confidence": "n/a"}

    return parsed


def run_catalyst_agent(candidates: list) -> list:
    """מקבל רשימת מועמדים מהסוכן הטכני, מוסיף מידע קטליזטור לכל אחד"""
    ticker_news = {}
    for c in candidates:
        ticker = c["ticker"]
        print(f"  שולף חדשות עבור {ticker}...")
        ticker_news[ticker] = fetch_news_finnhub(ticker, config.NEWS_LOOKBACK_HOURS)
        time.sleep(1)  # נימוס ל-Finnhub rate limit

    print("  שולח לסיווג LLM (קריאה אחת מרוכזת)...")
    classifications = classify_catalysts(ticker_news)

    enriched = []
    for c in candidates:
        ticker = c["ticker"]
        classification = classifications.get(
            ticker, {"catalyst_tier": "D", "catalyst_type": "unknown", "confidence": "n/a"}
        )
        enriched.append({**c, **classification, "news_count": len(ticker_news.get(ticker, []))})

    return enriched
