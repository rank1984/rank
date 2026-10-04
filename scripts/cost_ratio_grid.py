"""
טבלת cost_ratio לפי מחיר x עמלה (מספר רציף, לא רק עבר/לא עבר). הרצה: python scripts/cost_ratio_grid.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from agents.trade_plan import plan_trade  # noqa: E402

PRICES = [5, 8, 10, 15, 20, 30]
COMMISSIONS = [0.35, 0.5, 1.0, 1.5, 2.0, 3.0]

print(f"cost_ratio = (2*עמלה + slippage כניסה {config.SLIPPAGE_ENTRY_PCT:.2%} + slippage סטופ "
      f"{config.SLIPPAGE_STOP_PCT:.2%}) / R | סף: {config.MAX_COST_RATIO}")
print(f"סטופ {config.STOP_LOSS_PCT:.0%}, סיכון מתוכנן ${config.RISK_PER_TRADE_DOLLARS:.0f}, "
      f"תקרת פוזיציה {config.MAX_POSITION_VALUE_PCT:.0%} מ-${config.TOTAL_BUDGET}\n")
header = "מחיר  qty    R($)  " + "".join(f"${c:<7}" for c in COMMISSIONS)
print(header)
print("-" * len(header))
for p in PRICES:
    base = plan_trade(float(p), commission=None)
    cells = []
    for c in COMMISSIONS:
        plan = plan_trade(float(p), commission=c)
        cr = plan["cost_ratio"]
        cells.append(f"{cr:.2f}{'✓' if cr <= config.MAX_COST_RATIO else '✗'}   ")
    print(f"{p:<5} {base['qty']:<5} {base['risk_dollars']:<6} " + "".join(cells))
print("\n✓ = עובר את הסף, ✗ = נדחה. הסף קבוע (לא מכוונים אותו כדי שהשער יעבור).")
print("שימו לב: סביב הסף התוצאה רגישה להנחות ה-slippage. להחליף אותן בערכים מ-fills.csv אחרי 20+ fills.")
