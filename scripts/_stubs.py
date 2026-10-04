"""Stub ל-yfinance לבדיקות - חייב להיות מותקן לפני ייבוא agents.screener_agent"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)


class FakeTicker:
    registry: dict = {}   # ticker -> {"df": DataFrame, "info": dict | Exception}

    def __init__(self, ticker):
        self.t = ticker

    def history(self, period=None):
        return FakeTicker.registry[self.t]["df"].copy()   # KeyError = שגיאת שליפה

    @property
    def info(self):
        v = FakeTicker.registry[self.t].get("info", {})
        if isinstance(v, Exception):
            raise v
        return v


def install(registry: dict, spy_df):
    FakeTicker.registry = registry
    mod = types.ModuleType("yfinance")
    mod.Ticker = FakeTicker
    mod.download = lambda *a, **k: spy_df.copy()
    sys.modules["yfinance"] = mod
    return mod


def no_sleep():
    import agents.screener_agent as sa
    sa._sleep = lambda s: None
