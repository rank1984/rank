"""
orchestrator.py - Main execution loop for Momentum MAS pipeline.
Coordinates screening, filtering, catalyst analysis, risk sizing, and notifications.
"""

import os
import csv
from datetime import datetime
import config
from utils import logger, expected_session_date
from agents.screener_agent import ScreenerAgent
from agents.catalyst_agent import CatalystAgent
from agents.risk_manager import RiskManager
from agents.trade_plan import TradePlanGenerator
from notifier import Notifier

def append_to_runs_log(session_date: str, total_screened: int, passed_filters: int, signals_generated: int, dry_run: bool):
    """Logs run metrics into logs/runs.csv."""
    file_exists = config.RUNS_LOG.exists()
    with open(config.RUNS_LOG, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "session_date", "total_screened", "passed_filters", "signals_generated", "dry_run"])
        writer.writerow([
            datetime.now().isoformat(),
            session_date,
            total_screened,
            passed_filters,
            signals_generated,
            str(dry_run)
        ])

def run_pipeline():
    session_date = expected_session_date()
    logger.info(f"Starting pipeline run for session: {session_date} (Dry Run: {config.DRY_RUN})")

    screener = ScreenerAgent()
    catalyst_agent = CatalystAgent()
    risk_mgr = RiskManager()
    trade_planner = TradePlanGenerator()
    notifier = Notifier()

    raw_candidates = screener.run_screening()
    total_screened = len(raw_candidates)
    
    filtered_candidates = screener.apply_p0_filters(raw_candidates)
    passed_filters = len(filtered_candidates)

    approved_plans = []
    for item in filtered_candidates:
        catalyst = catalyst_agent.analyze(item["ticker"])
        if catalyst.get("has_valid_catalyst", False):
            plan = trade_planner.create_plan(item, catalyst)
            sized_plan = risk_mgr.size_position(plan)
            if sized_plan.get("shares", 0) > 0:
                approved_plans.append(sized_plan)

    signals_generated = len(approved_plans)
    logger.info(f"Screened: {total_screened} | Passed Filters: {passed_filters} | Signals: {signals_generated}")

    if approved_plans and not config.DRY_RUN:
        notifier.send_trade_plans(approved_plans)

    append_to_runs_log(session_date, total_screened, passed_filters, signals_generated, config.DRY_RUN)
    logger.info("Pipeline run completed successfully.")

if __name__ == "__main__":
    run_pipeline()
