"""
agents/filters.py - P0 / Baseline filtering rules for candidate screening.
"""

from typing import Dict, Any, Tuple
import config


def passes_p0_filters(candidate: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Checks if a screened candidate satisfies baseline P0 filtering rules:
    - Price within [MIN_PRICE, MAX_PRICE]
    - Volume >= MIN_VOLUME
    - Relative Volume >= MIN_REL_VOLUME
    - Price Change % >= MIN_CHANGE_PCT
    - Market Cap within limits (or handles FAIL_CLOSED_MCAP_FLOAT if missing)
    - Float <= MAX_FLOAT (or handles FAIL_CLOSED_MCAP_FLOAT if missing)
    """
    ticker = candidate.get("ticker", "UNKNOWN")
    price = candidate.get("price", 0.0)
    volume = candidate.get("volume", 0)
    rel_vol = candidate.get("relative_volume", 0.0)
    change_pct = candidate.get("change_pct", 0.0)

    # Basic Price and Volume Rules
    if not (config.MIN_PRICE <= price <= config.MAX_PRICE):
        return False, f"{ticker}: Price ${price} out of range [{config.MIN_PRICE}, {config.MAX_PRICE}]"

    if volume < config.MIN_VOLUME:
        return False, f"{ticker}: Volume {volume} below minimum {config.MIN_VOLUME}"

    if rel_vol < config.MIN_REL_VOLUME:
        return False, f"{ticker}: Rel Volume {rel_vol} below minimum {config.MIN_REL_VOLUME}"

    if change_pct < config.MIN_CHANGE_PCT:
        return False, f"{ticker}: Change {change_pct}% below minimum {config.MIN_CHANGE_PCT}%"

    # Market Cap Check
    mcap = candidate.get("market_cap")
    if mcap is None:
        if config.FAIL_CLOSED_MCAP_FLOAT:
            return False, f"{ticker}: Market Cap missing (fail-closed)"
    else:
        if not (config.MIN_MARKET_CAP <= mcap <= config.MAX_MARKET_CAP):
            return False, f"{ticker}: Market Cap ${mcap} out of range"

    # Float Check
    float_shares = candidate.get("float")
    if float_shares is None:
        if config.FAIL_CLOSED_MCAP_FLOAT:
            return False, f"{ticker}: Float missing (fail-closed)"
    else:
        if float_shares > config.MAX_FLOAT:
            return False, f"{ticker}: Float {float_shares} exceeds max {config.MAX_FLOAT}"

    return True, "PASSED"
