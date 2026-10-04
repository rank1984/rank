"""מריץ את כל הבדיקות (כל אחת בתהליך נפרד). הרצה: python scripts/run_all_tests.py"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = ["test_p0_filters.py", "test_e2e_screen_ticker.py", "test_trade_sim.py",
         "test_backtest_run.py", "test_count_signals.py", "test_orchestrator_dryrun.py"]

failed = []
for t in TESTS:
    r = subprocess.run([sys.executable, os.path.join(HERE, t)], capture_output=True, text=True)
    status = "PASSED" if r.returncode == 0 else "FAILED"
    print(f"{status:<7} {t}")
    if r.returncode != 0:
        failed.append(t)
        print(r.stdout[-1500:])
        print(r.stderr[-1500:])
print("\nכל הבדיקות עברו" if not failed else f"\nנכשלו: {failed}")
sys.exit(1 if failed else 0)
