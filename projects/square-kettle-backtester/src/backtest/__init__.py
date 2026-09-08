
"""Backtest package for BackTester project."""

# Re-export the top-level API so callers can do:
#   from backtest import run_backtest
# instead of importing from the submodule.
from .run_backtest import run_backtest

__all__ = ["run_backtest"]
