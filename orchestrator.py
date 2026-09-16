"""
Orchestrator - מריץ את 3 הסוכנים ברצף:
Screener Agent -> Catalyst Agent -> Risk & Yield Manager -> Telegram + Log
"""

import os
import csv
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import config
from utils import load_universe
from agents.screener_agent import run_screener
from agents.catalyst_agent import run_catalyst_agent
from agents.risk_manager import run_risk_manager
from notifier import send_summary


def log_results(results: list):
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    file_exists = os.path.isfile(config.LOG_FILE)

    with open(config.LOG_FILE, "a", newline="", encoding="utf-8") as f:
        fieldnames = [
            "timestamp", "ticker", "approved", "price", "rsi", "rvol", "atr_pct",
            "dollar_volume_m", "market_cap_m", "float_m", "gap_pct",
            "relative_strength_pct", "benchmark_change_pct",
            "catalyst_tier", "catalyst_type", "confidence",
            "entry_price", "stop_loss_price", "take_profit_price", "take_profit_pct_used",
            "qty", "risk_dollars", "position_value",
            "risk_reward_net", "net_profit_after_tax", "net_loss_if_stopped", "reason",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        for r in results:
            row = {**r, "timestamp": datetime.now().isoformat()}
            writer.writerow(row)


def main():
    print("=" * 70)
    print(f"מערכת מולטי-סוכנים - סריקת מומנטום | {datetime.now().isoformat()}")
    print("=" * 70)

    universe = load_universe()

    print(f"\n[סוכן 1/3] Screener Agent - סורק {len(universe)} מניות...")
    candidates = run_screener(universe)
    print(f"  --> {len(candidates)} מניות עברו סינון טכני\n")

    if not candidates:
        print("אין מועמדות היום. מסיים.")
        send_summary([], len(universe), 0)
        return

    print(f"[סוכן 2/3] Catalyst Agent - מדרג קטליזטורים חדשותיים (A/B/C/D)...")
    enriched = run_catalyst_agent(candidates)
    strong_catalyst = [c for c in enriched if c.get("catalyst_tier") in ("A", "B")]
    print(f"  --> {len(strong_catalyst)} מתוך {len(enriched)} עם דירוג A/B\n")

    # Risk Manager עצמו כבר דוחה דירוג מתחת לסף (config.CATALYST_TIER_MIN_ACCEPTABLE),
    # אז מעבירים את כל המועמדים ותנו לו להחליט - שקיפות מלאה בלוג גם על הדחויים.
    print(f"[סוכן 3/3] Risk & Yield Manager - בודק כדאיות כלכלית + position sizing מבוסס-סיכון...")
    final_results = run_risk_manager(enriched)
    approved = [r for r in final_results if r["approved"]]
    print(f"  --> {len(approved)} עסקאות אושרו סופית\n")

    log_results(final_results)

    print("שולח התראות טלגרם...")
    send_summary(approved, len(universe), len(candidates))

    print("\n" + "=" * 70)
    print(f"סיכום: {len(universe)} נסרקו -> {len(candidates)} טכני "
          f"-> {len(strong_catalyst)} קטליזטור A/B -> {len(approved)} אושרו")
    print(f"נרשם ל-{config.LOG_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
