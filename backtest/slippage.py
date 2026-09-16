"""
מודלי החלקה. כניסה תמיד Long (buy), יציאה תמיד sell.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SlippageModel:
    name: str
    fixed_bps: float = 0.0       # 1 bp = 0.0001
    spread_mult: float = 0.0     # שבר מ-spread_pct
    vol_mult: float = 0.0        # שבר מ-(high-low)/close

    def _slip(self, spread_pct: float, bar_range_pct: float) -> float:
        return (
            self.fixed_bps / 10_000.0
            + self.spread_mult * spread_pct
            + self.vol_mult * bar_range_pct
        )

    def apply_entry(self, price: float, spread_pct: float, bar_range_pct: float) -> float:
        return price * (1.0 + self._slip(spread_pct, bar_range_pct))

    def apply_exit(self, price: float, spread_pct: float, bar_range_pct: float) -> float:
        return price * (1.0 - self._slip(spread_pct, bar_range_pct))

    def effective_bps(self, spread_pct: float, bar_range_pct: float) -> float:
        return self._slip(spread_pct, bar_range_pct) * 10_000.0


SCENARIOS = {
    "optimistic":   SlippageModel("optimistic",   fixed_bps=0.0,  spread_mult=0.0, vol_mult=0.0),
    "base":         SlippageModel("base",         fixed_bps=5.0,  spread_mult=0.5, vol_mult=0.0),
    "conservative": SlippageModel("conservative", fixed_bps=15.0, spread_mult=1.0, vol_mult=0.1),
}
