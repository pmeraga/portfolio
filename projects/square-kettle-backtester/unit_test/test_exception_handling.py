"""
Unit tests for exception handling improvements in run_backtest.py.

Tests the fixed exception handling for unrealized PnL calculation.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
import pandas as pd
import warnings
from datetime import datetime

from backtest.run_backtest import compute_unrealized_series_from_reports


class TestExceptionHandling:
    """Test suite for exception handling in unrealized PnL calculation."""

    def test_compute_unrealized_with_invalid_data_returns_empty(self):
        """Should return empty DataFrame when equity_curve is None."""
        result = compute_unrealized_series_from_reports(None, None)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["timestamp", "unrealized_pnl"]
        assert len(result) == 0

    def test_compute_unrealized_with_empty_equity_returns_empty(self):
        """Should return empty DataFrame when equity_curve is empty."""
        equity_curve = pd.DataFrame(columns=["timestamp", "equity_value"])
        positions_df = pd.DataFrame(columns=["ts_closed", "realized_pnl"])
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["timestamp", "unrealized_pnl"]
        assert len(result) == 0

    def test_compute_unrealized_with_missing_columns_handles_gracefully(self):
        """Should handle missing required columns in positions_df gracefully."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "equity_value": [100.0, 110.0]
        })
        # Missing required columns
        positions_df = pd.DataFrame({"other_column": [1, 2]})
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        # Should fallback to: unrealized = equity - initial_equity
        assert len(result) == 2
        assert result["unrealized_pnl"].iloc[0] == pytest.approx(0.0)
        assert result["unrealized_pnl"].iloc[1] == pytest.approx(10.0)

    def test_compute_unrealized_with_invalid_realized_pnl_formats(self):
        """Should handle various realized_pnl formats including strings."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "equity_value": [100.0, 110.0, 115.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-01 12:00", "2024-01-02 12:00"]),
            "realized_pnl": ["USD 10.50", "-5.25"]  # Formatted strings
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        # Should parse formatted strings correctly
        assert len(result) == 3
        # First value should be 0 (before any realization)
        assert result["unrealized_pnl"].iloc[0] == pytest.approx(0.0)

    def test_compute_unrealized_with_none_realized_pnl(self):
        """Should handle None values in realized_pnl column."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "equity_value": [100.0, 110.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-01 12:00"]),
            "realized_pnl": [None]  # None value
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        # None should be treated as 0
        assert len(result) == 2
        # After None realization, unrealized should still be calculated
        assert result["unrealized_pnl"].iloc[1] == pytest.approx(10.0)

    def test_compute_unrealized_accounting_identity(self):
        """Should verify accounting identity: unrealized = equity - equity0 - cum_realized."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime([
                "2024-01-01 10:00",
                "2024-01-01 11:00",
                "2024-01-01 12:00",
                "2024-01-01 13:00"
            ]),
            "equity_value": [100.0, 110.0, 105.0, 115.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-01 11:30", "2024-01-01 13:30"]),
            "realized_pnl": [10.0, 5.0]
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # Verify accounting identity at each point
        initial_equity = 100.0
        
        # t1 (10:00): 100 - 100 - 0 = 0
        assert result["unrealized_pnl"].iloc[0] == pytest.approx(0.0)
        
        # t2 (11:00): 110 - 100 - 0 = 10 (before 11:30 realization)
        assert result["unrealized_pnl"].iloc[1] == pytest.approx(10.0)
        
        # t3 (12:00): 105 - 100 - 10 = -5 (after 11:30 realization of +10)
        assert result["unrealized_pnl"].iloc[2] == pytest.approx(-5.0)
        
        # t4 (13:00): 115 - 100 - 10 = 5 (before 13:30 realization)
        # Note: merge_asof with direction='backward' means we use last known cum_realized
        assert result["unrealized_pnl"].iloc[3] == pytest.approx(5.0)

