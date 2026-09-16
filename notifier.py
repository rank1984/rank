"""
מנגנון התראות - שולח הודעה לטלגרם עם כל עסקה שאושרה
"""

import os
import requests


def send_telegram_message(text: str):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("  (טלגרם לא מוגדר - מדלג על שליחה)")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  שגיאת שליחת טלגרם: {e}")
        return False


def format_trade_alert(trade: dict) -> str:
    return (
        f"🎯 <b>איתות מומנטום: {trade['ticker']}</b>\n\n"
        f"💰 כניסה: ${trade['entry_price']}\n"
        f"🛑 סטופ-לוס: ${trade['stop_loss_price']}\n"
        f"🎯 יעד: ${trade['take_profit_price']} ({trade.get('take_profit_pct_used', '?')}%)\n"
        f"📊 כמות: {trade['qty']} מניות (${trade['position_value']})\n"
        f"⚠️ סיכון מתוכנן: ${trade.get('risk_dollars', '?')}\n\n"
        f"📈 RSI: {trade['rsi']} | RVOL: {trade['rvol']}x | ATR: {trade['atr_pct']}%\n"
        f"💪 עוצמה יחסית: {trade.get('relative_strength_pct', '?')}% "
        f"(מדד: {trade.get('benchmark_change_pct', '?')}%)\n"
        f"💵 מחזור דולרי: ${trade.get('dollar_volume_m', '?')}M | "
        f"Float: {trade.get('float_m', '?')}M\n"
        f"📰 קטליזטור: דרגה {trade.get('catalyst_tier', 'N/A')} - "
        f"{trade.get('catalyst_type', 'N/A')} (ביטחון: {trade.get('confidence', 'N/A')})\n\n"
        f"⚖️ יחס סיכון:סיכוי נטו: 1:{trade['risk_reward_net']}\n"
        f"💵 רווח נטו משוער (אחרי עמלות+מס): ${trade['net_profit_after_tax']}\n"
        f"⚠️ הפסד משוער אם סטופ-לוס: ${trade['net_loss_if_stopped']}\n\n"
        f"🕐 חלון החזקה: 1-3 ימים"
    )


def send_summary(approved_trades: list, total_screened: int, total_candidates: int):
    if not approved_trades:
        text = (
            f"🔍 סריקה הושלמה\n"
            f"נסרקו {total_screened} מניות, {total_candidates} עברו סינון טכני, "
            f"0 עברו את בדיקת הסיכון/תשואה.\n"
            f"אין עסקאות מומלצות היום."
        )
        send_telegram_message(text)
        return

    for trade in approved_trades:
        send_telegram_message(format_trade_alert(trade))
