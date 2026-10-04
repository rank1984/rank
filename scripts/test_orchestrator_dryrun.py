"""
ריצת orchestrator מלאה על stub (בלי רשת): לוגים, dedupe, runs.csv, חג/נר ישן, מיגרציה, approved_live.
הרצה: python scripts/test_orchestrator_dryrun.py
"""
import _stubs
import csv
import os
import tempfile
from datetime import date

import _synthetic as S

OK_INFO = {"marketCap": 300e6, "floatShares": 50e6}
REG = {
    "STRONG": {"df": S.make_strong(), "info": OK_INFO},
    "WEAK": {"df": S.make_weak(), "info": OK_INFO},
    "NOMCAP": {"df": S.make_strong(), "info": {}},
}
_stubs.install(REG, S.spy_frame(S.END, 0.0))
_stubs.no_sleep()

import config  # noqa: E402
import agents.screener_agent as sa  # noqa: E402
import orchestrator as orch  # noqa: E402

BAR = date(2026, 9, 28)


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fresh_env(d, commission=None):
    config.LOG_FILE = os.path.join(d, "decisions.csv")
    config.SCREENER_ALL_FILE = os.path.join(d, "screener_all.csv")
    config.RUNS_FILE = os.path.join(d, "runs.csv")
    config.MCAP_SNAPSHOT_FILE = os.path.join(d, "mcap_snapshot.csv")
    config.FILLS_FILE = os.path.join(d, "fills.csv")
    config.LLM_RAW_DIR = os.path.join(d, "llm_raw")
    config.LEGACY_LOG_FILE = os.path.join(d, "decisions_legacy.csv")
    config.UNIVERSE_FILE = os.path.join(d, "universe.csv")
    config.COMMISSION_PER_SIDE = commission
    with open(config.UNIVERSE_FILE, "w") as f:
        f.write("ticker\nSTRONG\nWEAK\nNOMCAP\nSTRONG\n")     # כולל כפילות
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "FORCE_RUN"):
        os.environ.pop(k, None)


def fake_catalyst(candidates, run_id=None, bar_date=None):
    return [{**c, "catalyst_tier": "A", "catalyst_type": "test", "confidence": "high",
             "classifier_source": "llm", "llm_provider": "t", "llm_model": "t", "prompt_hash": "x",
             "news_count": 3} for c in candidates]


orch.run_catalyst_agent = fake_catalyst

# --- 1. נר שונה מהצפוי (חג / נר חלקי): אין לוג החלטות, יש שורת ריצה ---
with tempfile.TemporaryDirectory() as d:
    fresh_env(d)
    sa.expected_session_date = lambda: date(2026, 9, 29)
    orch.main()
    assert not os.path.exists(config.LOG_FILE), "לא אמורות להיכתב החלטות"
    r = rows(config.RUNS_FILE)
    assert len(r) == 1 and r[0]["status"] == "no_new_bar", r
print("OK no_new_bar: runs.csv row, no decisions")

# --- 2. ריצה חיה תקינה, בלי עמלה: אות בלבד ---
with tempfile.TemporaryDirectory() as d:
    fresh_env(d, commission=None)
    sa.expected_session_date = lambda: BAR
    # לוג ישן עם כותרת ישנה -> מיגרציה
    with open(config.LOG_FILE, "w", encoding="utf-8") as f:
        f.write("timestamp,ticker,approved\n2026-01-01,OLD,True\n")
    orch.main()
    dec = rows(config.LOG_FILE)
    assert os.path.exists(config.LEGACY_LOG_FILE) and "OLD" in open(config.LEGACY_LOG_FILE, encoding="utf-8").read()
    assert len(dec) == 1 and dec[0]["ticker"] == "STRONG", dec
    d0 = dec[0]
    assert d0["signal_date"] == "2026-09-28" and d0["run_mode"] == "live"
    assert d0["approved_signal"] == "1" and d0["approved_live"] == "0" and d0["reason"] == "commission_not_set"
    assert d0["strategy_version"] == config.STRATEGY_VERSION and d0["classifier_source"] == "llm"
    assert float(d0["stop_loss_price"]) > 0 and int(d0["qty"]) >= 1
    allr = rows(config.SCREENER_ALL_FILE)
    assert len(allr) == 3, len(allr)                      # הכפילות ב-universe הוסרה
    by = {r["ticker"]: r for r in allr}
    assert by["STRONG"]["passed"] == "1" and "no_ema_breakout" in by["WEAK"]["all_failed"]
    assert by["NOMCAP"]["all_failed"] == "missing_mcap_or_float" and by["NOMCAP"]["mcap_missing"] == "1"
    assert len(rows(config.MCAP_SNAPSHOT_FILE)) == 3
    run = rows(config.RUNS_FILE)[-1]
    assert run["status"] == "ok" and run["approved_signal"] == "1" and run["approved_live"] == "0"
    assert run["commission_set"] == "0" and run["scanned"] == "3"

    # --- 3. ריצה שנייה על אותו נר: יוצאת בלי כתיבה ---
    n_dec, n_all, n_runs = len(rows(config.LOG_FILE)), len(rows(config.SCREENER_ALL_FILE)), len(rows(config.RUNS_FILE))
    orch.main()
    assert (len(rows(config.LOG_FILE)), len(rows(config.SCREENER_ALL_FILE)), len(rows(config.RUNS_FILE))) == (n_dec, n_all, n_runs)
print("OK live run: logs, legacy migration, universe dedupe, rerun writes nothing")

# --- 4. FORCE_RUN: dedupe של החלטות לפי (signal_date, ticker, run_mode) ---
with tempfile.TemporaryDirectory() as d:
    fresh_env(d)
    sa.expected_session_date = lambda: date(2026, 9, 29)   # היה נעצר בלי force
    os.environ["FORCE_RUN"] = "1"
    orch.main()
    orch.main()
    dec = rows(config.LOG_FILE)
    assert len(dec) == 1 and dec[0]["run_mode"] == "force", dec
print("OK force mode: run_mode=force, no duplicate decisions")

# --- 5. עם עמלה שעוברת את השער: approved_live ---
with tempfile.TemporaryDirectory() as d:
    fresh_env(d, commission=0.5)
    sa.expected_session_date = lambda: BAR
    orch.main()
    d0 = rows(config.LOG_FILE)[0]
    assert d0["approved_live"] == "1" and d0["cost_gate_pass"] == "1" and d0["reason"] == "approved_live", d0
print("OK commission set and gate passes -> approved_live")

# --- 6. נכשל בשליפה של הכול: נרשם ולא קורס ---
with tempfile.TemporaryDirectory() as d:
    fresh_env(d)
    sa.expected_session_date = lambda: BAR
    _stubs.FakeTicker.registry = {}
    orch.main()
    run = rows(config.RUNS_FILE)[-1]
    assert run["status"] == "ok" and run["passed_technical"] == "0" and run["fetch_errors"] == "3", run
print("OK all fetch failures are recorded in runs.csv (not silent)")
print("test_orchestrator_dryrun PASSED")
