"""
config.py - Configuration management for Momentum MAS workflow
Reads settings from environment variables and defines system-wide constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# File Paths
UNIVERSE_FILE = BASE_DIR / "universe.csv"
FILLS_LOG = LOGS_DIR / "fills.csv"
RUNS_LOG = LOGS_DIR / "runs.csv"

# API Keys & Secrets
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Workflow & Execution Settings
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
FAIL_CLOSED_MCAP_FLOAT = os.getenv("FAIL_CLOSED_MCAP_FLOAT", "true").lower() == "true"
STRICT_CATALYST_DAYS = int(os.getenv("STRICT_CATALYST_DAYS", "7"))

# Strategy / Screener Thresholds (P0 / Baseline)
MIN_PRICE = float(os.getenv("MIN_PRICE", "2.0"))
MAX_PRICE = float(os.getenv("MAX_PRICE", "20.0"))
MIN_VOLUME = int(os.getenv("MIN_VOLUME", "100000"))
MIN_REL_VOLUME = float(os.getenv("MIN_REL_VOLUME", "1.5"))
MIN_CHANGE_PCT = float(os.getenv("MIN_CHANGE_PCT", "10.0"))

# Market Cap & Float Limits
MIN_MARKET_CAP = float(os.getenv("MIN_MARKET_CAP", "10000000"))      # $10M
MAX_MARKET_CAP = float(os.getenv("MAX_MARKET_CAP", "1000000000"))    # $1B
MAX_FLOAT = float(os.getenv("MAX_FLOAT", "50000000"))                # 50M shares

# Risk Management Parameters
MAX_PORTFOLIO_RISK_PCT = float(os.getenv("MAX_PORTFOLIO_RISK_PCT", "2.0"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "3"))
DEFAULT_ACCOUNT_SIZE = float(os.getenv("DEFAULT_ACCOUNT_SIZE", "10000.0"))

# Timezone / Market Schedule
MARKET_TIMEZONE = "America/New_York"
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
