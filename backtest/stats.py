"""סטטיסטיקה קטנה: bootstrap CI לממוצע (Expectancy ב-R)."""
import numpy as np


def bootstrap_ci_mean(values, n_boot: int = 5000, alpha: float = 0.10, seed: int = 7):
    """(lo, mean, hi). alpha=0.10 -> רווח סמך 90%. מחזיר None אם אין נתונים."""
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    if arr.size == 0:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n_boot, arr.size))
    means = arr[idx].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(arr.mean()), float(np.quantile(means, 1 - alpha / 2))
