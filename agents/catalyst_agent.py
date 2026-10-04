"""
סוכן 2: Catalyst Agent
שולף חדשות מ-Finnhub ומדרג A/B/C/D דרך LLM בקריאה אחת מרוכזת.

שינויים מהגרסה הקודמת:
- temperature=0 (Gemini ו-Groq)
- classifier_source: llm | keyword_fallback | no_news | llm_invalid
- אימות סכמה: טיקר חסר / tier לא חוקי -> D עם llm_invalid
- שמירת prompt_hash + תשובה גולמית ב-logs/llm_raw/
- מפתח Gemini נשלח בכותרת, לא ב-URL
"""
import hashlib
import json
import os
import time
from datetime import datetime, timedelta

import requests

import config

VALID_TIERS = ("A", "B", "C", "D")


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
    except Exception as e:  # noqa: BLE001
        print(f"    שגיאת Finnhub עבור {ticker}: {e}")
        return []

    cutoff = datetime.now() - timedelta(hours=hours)
    recent = []
    for a in articles[:10]:
        pub_time = datetime.fromtimestamp(a.get("datetime", 0))
        if pub_time >= cutoff:
            recent.append({"headline": a.get("headline", ""), "summary": (a.get("summary", "") or "")[:200]})
    return recent


def _call_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("no_gemini_key")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent"
    )
    headers = {"x-goog-api-key": api_key}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0},
    }
    resp = requests.post(url, headers=headers, json=body, timeout=30)
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
        "temperature": 0,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _classify_tier_by_keywords(text: str) -> tuple:
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
    """סיווג מבוסס מילות מפתח (בלי שלילה/סנטימנט) - לא מאושר לעסקאות כברירת מחדל."""
    results = {}
    for ticker, articles in ticker_news.items():
        if not articles:
            results[ticker] = _no_news()
            continue
        text = " ".join(a["headline"] + " " + a["summary"] for a in articles)
        tier, matched = _classify_tier_by_keywords(text)
        results[ticker] = {
            "catalyst_tier": tier,
            "catalyst_type": matched,
            "confidence": "low_keyword_based",
            "classifier_source": "keyword_fallback",
        }
    return results


def _no_news() -> dict:
    return {"catalyst_tier": "D", "catalyst_type": "no_news", "confidence": "n/a",
            "classifier_source": "no_news"}


def _build_prompt(tickers_with_news: dict) -> str:
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
    return prompt


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no_json_object")
    return json.loads(cleaned[start:end + 1])


def classify_catalysts(ticker_news: dict):
    """
    מחזיר (classifications, meta).
    classifications[ticker] = {catalyst_tier, catalyst_type, confidence, classifier_source}
    meta = {provider, model, prompt_hash, prompt, raw_response, error}
    """
    meta = {"provider": "none", "model": "none", "prompt_hash": "", "prompt": "", "raw_response": None, "error": None}

    tickers_with_news = {t: arts for t, arts in ticker_news.items() if arts}
    out = {t: _no_news() for t in ticker_news if t not in tickers_with_news}
    if not tickers_with_news:
        return out, meta

    prompt = _build_prompt(tickers_with_news)
    meta["prompt"] = prompt
    meta["prompt_hash"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    meta["provider"] = config.LLM_PROVIDER
    meta["model"] = config.GEMINI_MODEL if config.LLM_PROVIDER == "gemini" else config.GROQ_MODEL

    try:
        raw = _call_gemini(prompt) if config.LLM_PROVIDER == "gemini" else _call_groq(prompt)
        meta["raw_response"] = raw
    except Exception as e:  # noqa: BLE001
        print(f"    LLM נכשל ({e}), עובר ל-keyword fallback")
        meta["error"] = f"llm_call:{e}"
        out.update(_keyword_fallback(tickers_with_news))
        return out, meta

    try:
        parsed = _parse_json(raw)
    except Exception as e:  # noqa: BLE001
        print(f"    שגיאת פרסור JSON מה-LLM ({e}), עובר ל-keyword fallback")
        meta["error"] = f"llm_parse:{e}"
        out.update(_keyword_fallback(tickers_with_news))
        return out, meta

    parsed_upper = {str(k).upper().strip(): v for k, v in parsed.items()}
    for t in tickers_with_news:
        entry = parsed_upper.get(t.upper())
        tier = str(entry.get("catalyst_tier", "")).upper().strip() if isinstance(entry, dict) else ""
        if tier in VALID_TIERS:
            out[t] = {
                "catalyst_tier": tier,
                "catalyst_type": str(entry.get("catalyst_type", ""))[:120],
                "confidence": str(entry.get("confidence", "")),
                "classifier_source": "llm",
            }
        else:
            out[t] = {"catalyst_tier": "D", "catalyst_type": "llm_invalid", "confidence": "n/a",
                      "classifier_source": "llm_invalid"}
    return out, meta


def _save_raw(meta: dict, run_id, bar_date) -> None:
    if not meta.get("prompt"):
        return
    try:
        os.makedirs(config.LLM_RAW_DIR, exist_ok=True)
        name = f"{bar_date}_{run_id}.json".replace(":", "-")
        with open(os.path.join(config.LLM_RAW_DIR, name), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        print(f"    לא ניתן לשמור raw response: {e}")


def run_catalyst_agent(candidates: list, run_id=None, bar_date=None) -> list:
    """מוסיף לכל מועמד מידע קטליזטור + מטא-דאטה של הסיווג"""
    ticker_news = {}
    for c in candidates:
        ticker = c["ticker"]
        print(f"  שולף חדשות עבור {ticker}...")
        ticker_news[ticker] = fetch_news_finnhub(ticker, config.NEWS_LOOKBACK_HOURS)
        time.sleep(1)

    print("  שולח לסיווג LLM (קריאה אחת מרוכזת)...")
    classifications, meta = classify_catalysts(ticker_news)
    _save_raw(meta, run_id, bar_date)

    enriched = []
    for c in candidates:
        ticker = c["ticker"]
        cls = classifications.get(ticker, {**_no_news(), "catalyst_type": "unknown"})
        enriched.append({
            **c, **cls,
            "news_count": len(ticker_news.get(ticker, [])),
            "llm_provider": meta["provider"],
            "llm_model": meta["model"],
            "prompt_hash": meta["prompt_hash"],
        })
    return enriched
