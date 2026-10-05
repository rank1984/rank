"""
agents/screener_agent.py - Agent responsible for scanning universe and applying filters.
"""

import csv
from typing import List, Dict, Any
import config
from utils import logger
from agents.filters import passes_p0_filters


class ScreenerAgent:
    def __init__(self, universe_path=None):
        self.universe_path = universe_path or config.UNIVERSE_FILE

    def run_screening(self) -> List[Dict[str, Any]]:
        """Reads universe candidates from CSV or data source."""
        candidates = []
        if not self.universe_path.exists():
            logger.warning(f"Universe file not found at {self.universe_path}")
            return candidates

        with open(self.universe_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    candidates.append({
                        "ticker": row.get("ticker", "").upper(),
                        "price": float(row.get("price", 0.0)),
                        "volume": int(row.get("volume", 0)),
                        "relative_volume": float(row.get("relative_volume", 0.0)),
                        "change_pct": float(row.get("change_pct", 0.0)),
                        "market_cap": float(row["market_cap"]) if row.get("market_cap") else None,
                        "float": float(row["float"]) if row.get("float") else None,
                    })
                except ValueError as e:
                    logger.debug(f"Skipping row due to parsing error: {e}")
                    continue

        return candidates

    def apply_p0_filters(self, raw_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters candidates using passes_p0_filters logic."""
        passed = []
        for candidate in raw_candidates:
            ok, reason = passes_p0_filters(candidate)
            if ok:
                passed.append(candidate)
            else:
                logger.debug(f"Candidate rejected: {reason}")
        return passed
