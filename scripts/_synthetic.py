"""נתוני דמה לבדיקות (בלי רשת). שני מקרים: strong (עובר את כל הפילטרים) ו-weak (נכשל בכמה)."""
import numpy as np
import pandas as pd

N = 70
END = "2026-09-28"


def _index(n=N, end=END):
    return pd.bdate_range(end=end, periods=n)


def make_strong(seed: int = 149, n: int = N) -> pd.DataFrame:
    """מגמה עולה קלה ואז gap-up של ~8% בנר האחרון עם נפח גבוה"""
    rng = np.random.default_rng(seed)
    idx = _index(n)
    close = np.empty(n)
    close[0] = 9.0
    for i in range(1, n - 1):
        close[i] = close[i - 1] * (1 + rng.normal(0.003, 0.012))
    close[-1] = close[-2] * 1.085
    open_ = np.empty(n)
    open_[1:] = close[:-1] * (1 + rng.normal(0.0, 0.004, n - 1))
    open_[0] = close[0]
    open_[-1] = close[-2] * 1.07
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0.012, 0.004, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0.012, 0.004, n)))
    vol = np.full(n, 3_000_000.0)
    vol[-1] = 12_000_000.0
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def make_weak(n: int = N) -> pd.DataFrame:
    """מגמת ירידה, נפח רגיל, gap חיובי בנר האחרון (הפרמטרים שהוכיחו את באג ה-elif)"""
    idx = _index(n)
    close = np.linspace(14.0, 9.3, n)
    close[-1] = 10.0
    open_ = close.copy()
    open_[-1] = close[-2] * 1.08
    return pd.DataFrame({"Open": open_, "High": close * 1.02, "Low": close * 0.98,
                         "Close": close, "Volume": np.full(n, 3_000_000.0)}, index=idx)


def spy_frame(bar_date=END, change=0.0):
    idx = pd.bdate_range(end=bar_date, periods=2)
    return pd.DataFrame({"Close": [100.0, 100.0 * (1 + change)]}, index=idx)


def spy_full(like: pd.DataFrame, change_last: float = 0.0) -> pd.DataFrame:
    """SPY שטוח (שינוי 0) לאורך כל האינדקס, עם שינוי אופציונלי בנר האחרון"""
    close = np.full(len(like), 100.0)
    close[-1] = 100.0 * (1 + change_last)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close,
                         "Volume": np.full(len(like), 1e8)}, index=like.index)
