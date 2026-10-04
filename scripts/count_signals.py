"""
P0b - ספירת מועמדים טכניים היסטורית (להערכת קצב אותות לפני paper). לא מודד Edge.

    python scripts/count_signals.py --days 90 [--with-outcomes]

שתי ריצות:
  without_mcap_float          - כל הפילטרים הטכניים, בלי mcap/float
  with_mcap_float_current     - בנוסף mcap/float של *היום* (look-ahead, מסומן lookahead_mcap_float=1)

Tier A לא ניתן לספירה אחורה (אין חדשות היסטוריות / דירוג LLM). את שיעור ה-Tier A מעריכים
מנתוני ה-shadow החיים הראשונים.
"""
import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

import config  # noqa: E402
from agents.filters import CHECK_ORDER, add_indicators, evaluate_filters, features_at  # noqa: E402

WARMUP_BARS = 30


def evaluate_window(data: dict, spy: pd.DataFrame, window_start, infos: dict | None, use_mcap: bool) -> list:
    """שורה לכל (טיקר, יום) בחלון, עם כל הפילטרים שנכשלו."""
    spy_change = spy["Close"].pct_change()
    rows = []
    for ticker, df in data.items():
        if ticker == "SPY":
            continue
        ind = add_indicators(df)
        for pos in range(max(1, WARMUP_BARS), len(ind)):
            d = ind.index[pos]
            if d < window_start:
                continue
            sc = spy_change.get(d)
            if sc is None or pd.isna(sc):
                continue
            f = features_at(ind, pos, float(sc))
            if f is None:
                continue
            if use_mcap:
                mc, fl = (infos or {}).get(ticker, (None, None))
                failed = evaluate_filters(f, mc, fl, check_mcap_float=True)
            else:
                failed = evaluate_filters(f, check_mcap_float=False)
            nxt_open = float(ind["Open"].iloc[pos + 1]) if pos + 1 < len(ind) else None
            rows.append({
                "bar_date": pd.Timestamp(d).date().isoformat(),
                "ticker": ticker,
                "passed": not failed,
                "all_failed": ";".join(failed),
                "price": round(f["price"], 2),
                "rsi": None if f["rsi"] is None else round(f["rsi"], 1),
                "rvol": round(f["rvol"], 2),
                "gap_pct": round(f["gap_pct"] * 100, 2),
                "atr_pct": None if f["atr_pct"] is None else round(f["atr_pct"] * 100, 2),
                "relative_strength_pct": round(f["relative_strength"] * 100, 2),
                "dollar_volume_m": round(f["dollar_volume"] / 1e6, 1),
                "entry_gap_vs_signal_close_pct": None if nxt_open is None else round((nxt_open / f["price"] - 1) * 100, 2),
                "lookahead_mcap_float": int(use_mcap),
                "_pos": pos,
            })
    return rows


def funnel(rows: list, use_mcap: bool) -> pd.DataFrame:
    names = [n for n in CHECK_ORDER if use_mcap or n not in
             ("missing_mcap_or_float", "market_cap_out_of_range", "float_out_of_range")]
    total = len(rows)
    sets = [set(r["all_failed"].split(";")) if r["all_failed"] else set() for r in rows]
    remaining = list(range(total))
    out = []
    for n in names:
        alone = sum(1 for s in sets if n in s)
        remaining = [i for i in remaining if n not in sets[i]]
        out.append({"filter": n, "fails_individually": alone, "remaining_after_cumulative": len(remaining)})
    return pd.DataFrame(out)


def summarize(name: str, rows: list, fun: pd.DataFrame, fetch_failed: list, with_outcomes: str = "") -> str:
    cands = [r for r in rows if r["passed"]]
    days = sorted({r["bar_date"] for r in rows})
    by_month = Counter(r["bar_date"][:7] for r in cands)
    cand_set = {(r["ticker"], r["bar_date"]) for r in cands}
    consecutive = 0
    all_dates = days
    prev = {d: all_dates[i - 1] for i, d in enumerate(all_dates) if i > 0}
    for r in cands:
        pd_ = prev.get(r["bar_date"])
        if pd_ and (r["ticker"], pd_) in cand_set:
            consecutive += 1
    weeks = max(len(days) / 5.0, 1e-9)
    lines = [
        f"=== {name} ===",
        f"ימי מסחר אפקטיביים בחלון: {len(days)}",
        f"מועמדים טכניים בסך הכל: {len(cands)}",
        f"ממוצע מועמדים בשבוע: {len(cands) / weeks:.2f}",
        f"טיקרים ייחודיים: {len({r['ticker'] for r in cands})}",
        f"מועמדים שהם אותו טיקר ביום עוקב: {consecutive} ({(100 * consecutive / len(cands)) if cands else 0:.0f}%)",
        "לפי חודש: " + (", ".join(f"{k}: {v}" for k, v in sorted(by_month.items())) or "אין"),
        f"טיקרים שנכשלה שליפתם: {', '.join(fetch_failed) or 'אין'}",
        "",
        "Funnel:",
        fun.to_string(index=False),
        "",
        "הערה: Tier A אינו ניתן לספירה היסטורית. mcap/float (אם נבדקו) הם של היום - look-ahead.",
        "הערה: יקום עם survivorship bias; החלון האפקטיבי קצר מ-90 יום בגלל חימום האינדיקטורים.",
    ]
    if with_outcomes:
        lines += ["", with_outcomes]
    return "\n".join(lines)


def outcomes_text(data: dict, cands: list, out_path: str) -> str:
    from backtest.engine import simulate_trade
    res = []
    for r in cands:
        df = data[r["ticker"]]
        c = {"ticker": r["ticker"], "date": pd.Timestamp(r["bar_date"]), "price": r["price"], "rvol": r["rvol"],
             "relative_strength_pct": r["relative_strength_pct"], "rsi": r["rsi"] or 0,
             "gap_pct": r["gap_pct"], "atr_pct": r["atr_pct"] or 0}
        t = simulate_trade(c, df)
        if t["status"] == "closed":
            res.append(t)
    pd.DataFrame(res).to_csv(out_path, index=False)
    reasons = Counter(t["exit_reason"] for t in res)
    return (f"[DESCRIPTIVE_ONLY] outcomes אינפורמטיביים בלבד (לא ראיה ל-Edge): נסגרו {len(res)} עסקאות, "
            f"יציאות: {dict(reasons)}")


def download_all(tickers: list, start: str, end: str):
    import yfinance as yf
    data, failed = {}, []
    for t in ["SPY"] + tickers:
        try:
            df = yf.download(t, start=start, end=end, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) > WARMUP_BARS + 5:
                data[t] = df
            else:
                failed.append(t)
        except Exception:  # noqa: BLE001
            failed.append(t)
    return data, failed


def fetch_infos(tickers: list) -> dict:
    import yfinance as yf
    from agents.screener_agent import fetch_market_info
    infos = {}
    for t in tickers:
        mc, fl, _ = fetch_market_info(yf.Ticker(t))
        infos[t] = (mc, fl)
    return infos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--universe", default=config.UNIVERSE_FILE)
    ap.add_argument("--out", default="logs/signal_count")
    ap.add_argument("--with-outcomes", action="store_true")
    args = ap.parse_args()

    config.UNIVERSE_FILE = args.universe
    from utils import load_universe
    tickers = load_universe()

    today = datetime.now()
    start_dl = (today - timedelta(days=args.days + 130)).strftime("%Y-%m-%d")
    end_dl = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    window_start = pd.Timestamp(today - timedelta(days=args.days))

    print(f"מוריד נתונים ל-{len(tickers)} טיקרים ({start_dl} -> {end_dl})...")
    data, failed = download_all(tickers, start_dl, end_dl)
    if "SPY" not in data:
        print("שגיאה: SPY לא הורד")
        return
    spy = data["SPY"]
    os.makedirs(args.out, exist_ok=True)

    print("מביא mcap/float נוכחיים (look-ahead)...")
    infos = fetch_infos([t for t in data if t != "SPY"])

    for name, use_mcap in (("without_mcap_float", False), ("with_mcap_float_current", True)):
        rows = evaluate_window(data, spy, window_start, infos if use_mcap else None, use_mcap)
        fun = funnel(rows, use_mcap)
        cands = [r for r in rows if r["passed"]]
        pd.DataFrame(cands).drop(columns=["_pos"], errors="ignore").to_csv(
            os.path.join(args.out, f"candidates_{name}.csv"), index=False)
        fun.to_csv(os.path.join(args.out, f"funnel_{name}.csv"), index=False)
        extra = outcomes_text(data, cands, os.path.join(args.out, f"outcomes_{name}.csv")) if args.with_outcomes else ""
        text = summarize(name, rows, fun, failed, extra)
        with open(os.path.join(args.out, f"summary_{name}.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        print("\n" + text)


if __name__ == "__main__":
    main()
