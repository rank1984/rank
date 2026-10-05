"""
utils.py - General utility functions for logging, date handling, and calculations.
"""

import logging
from datetime import datetime
import pytz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MomentumMAS")

def get_ny_now() -> datetime:
    """Returns the current datetime in New York (America/New_York) timezone."""
    ny_tz = pytz.timezone("America/New_York")
    return datetime.now(ny_tz)

def expected_session_date(dt: datetime = None) -> str:
    """
    Returns the expected trading session date string (YYYY-MM-DD) in NY timezone.
    If no datetime is supplied, uses current NY time.
    """
    if dt is None:
        dt = get_ny_now()
    elif dt.tzinfo is None:
        ny_tz = pytz.timezone("America/New_York")
        dt = ny_tz.localize(dt)
    else:
        dt = dt.astimezone(pytz.timezone("America/New_York"))
    
    return dt.strftime("%Y-%m-%d")

def calculate_position_size(account_size: float, risk_pct: float, entry_price: float, stop_loss: float) -> int:
    """Calculates position size in shares based on account risk."""
    if entry_price <= stop_loss or entry_price <= 0:
        return 0
    risk_per_share = entry_price - stop_loss
    max_risk_amount = account_size * (risk_pct / 100.0)
    shares = int(max_risk_amount / risk_per_share)
    return max(shares, 0)
