"""
Unit tests for run_backtest.py functions.

Tests mathematical calculations and data transformations to ensure correctness.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
import pandas as pd
from datetime import datetime

from backtest.run_backtest import (
    _parse_money_to_float,
    _pick_metric,
    _extract_timestamped_series_from_account,
    _compute_total_return_and_mdd,
    compute_unrealized_series_from_reports,
)


class TestParseMoneyToFloat:
    """Test suite for _parse_money_to_float function."""

    def test_parse_integer(self):
        """Should parse integer to float."""
        assert _parse_money_to_float(123) == 123.0

    def test_parse_float(self):
        """Should parse float directly."""
        assert _parse_money_to_float(123.45) == 123.45

    def test_parse_negative_float(self):
        """Should parse negative float."""
        assert _parse_money_to_float(-123.45) == -123.45

    def test_parse_string_plain_number(self):
        """Should parse plain numeric string."""
        assert _parse_money_to_float("123.45") == 123.45

    def test_parse_string_negative_number(self):
        """Should parse negative numeric string."""
        assert _parse_money_to_float("-123.45") == -123.45

    def test_parse_string_with_currency(self):
        """Should extract number from currency-formatted string."""
        assert _parse_money_to_float("USD 123.45") == 123.45

    def test_parse_string_with_currency_negative(self):
        """Should extract negative number from currency string."""
        assert _parse_money_to_float("USD -123.45") == -123.45

    def test_parse_string_complex_format(self):
        """Should extract number from complex formatted string."""
        # Regex looks for first numeric pattern
        assert _parse_money_to_float("Balance: $123.45 USD") == 123.45

    def test_parse_none_returns_none(self):
        """Should return None for None input."""
        assert _parse_money_to_float(None) is None

    def test_parse_empty_string_returns_none(self):
        """Should return None for empty string."""
        assert _parse_money_to_float("") is None

    def test_parse_invalid_string_returns_none(self):
        """Should return None for non-numeric string."""
        assert _parse_money_to_float("invalid") is None

    def test_parse_string_no_number_returns_none(self):
        """Should return None for string with no numbers."""
        assert _parse_money_to_float("USD") is None

    def test_parse_zero(self):
        """Should parse zero correctly."""
        assert _parse_money_to_float(0) == 0.0
        assert _parse_money_to_float("0") == 0.0
        assert _parse_money_to_float("0.0") == 0.0

    def test_parse_scientific_notation(self):
        """Should handle scientific notation if present."""
        # The regex pattern will extract the first numeric part
        result = _parse_money_to_float("1.23e2")
        assert result == 1.23  # Extracts "1.23" from the pattern


class TestPickMetric:
    """Test suite for _pick_metric function."""

    def test_exact_match(self):
        """Should find metric with exact key match."""
        stats = {"Sharpe Ratio": 1.5}
        result = _pick_metric(stats, ["Sharpe Ratio"])
        assert result == 1.5

    def test_case_insensitive_match(self):
        """Should find metric with case-insensitive match."""
        stats = {"Sharpe Ratio": 2.0}
        result = _pick_metric(stats, ["sharpe ratio"])
        assert result == 2.0

    def test_case_insensitive_upper(self):
        """Should find metric when candidate is uppercase."""
        stats = {"sharpe ratio": 1.8}
        result = _pick_metric(stats, ["SHARPE RATIO"])
        assert result == 1.8

    def test_mixed_case_variations(self):
        """Should handle mixed case variations."""
        stats = {"ShaRPe RaTio": 1.2}
        result = _pick_metric(stats, ["sharpe ratio"])
        assert result == 1.2

    def test_first_match_wins(self):
        """Should return first matching candidate."""
        stats = {"Sharpe Ratio": 1.5, "Sharpe": 2.0}
        result = _pick_metric(stats, ["Sharpe Ratio", "Sharpe"])
        assert result == 1.5

    def test_second_candidate_matches(self):
        """Should try candidates in order until match found."""
        stats = {"Sharpe": 2.5}
        result = _pick_metric(stats, ["Sharpe Ratio", "Sharpe"])
        assert result == 2.5

    def test_float_conversion_from_int(self):
        """Should convert integer to float."""
        stats = {"Win Rate": 75}
        result = _pick_metric(stats, ["Win Rate"])
        assert result == 75.0
        assert isinstance(result, float)

    def test_float_conversion_from_string(self):
        """Should convert numeric string to float."""
        stats = {"Profit Factor": "1.5"}
        result = _pick_metric(stats, ["Profit Factor"])
        assert result == 1.5

    def test_non_float_value_returned_as_is(self):
        """Should return non-numeric value as-is when float conversion fails."""
        stats = {"Status": "Active"}
        result = _pick_metric(stats, ["Status"])
        assert result == "Active"

    def test_missing_key_returns_none(self):
        """Should return None when no candidates match."""
        stats = {"Sharpe Ratio": 1.5}
        result = _pick_metric(stats, ["Win Rate", "Profit Factor"])
        assert result is None

    def test_empty_dict_returns_none(self):
        """Should return None for empty stats dict."""
        stats = {}
        result = _pick_metric(stats, ["Sharpe Ratio"])
        assert result is None

    def test_empty_candidates_returns_none(self):
        """Should return None for empty candidates list."""
        stats = {"Sharpe Ratio": 1.5}
        result = _pick_metric(stats, [])
        assert result is None

    def test_partial_match_does_not_match(self):
        """Should not match partial key names."""
        stats = {"Sharpe Ratio (252 days)": 1.5}
        result = _pick_metric(stats, ["Sharpe"])
        assert result is None

    def test_multiple_stats_picks_correct_one(self):
        """Should find correct metric from multiple stats."""
        stats = {
            "Total Return": 0.25,
            "Sharpe Ratio": 1.5,
            "Max Drawdown": -0.15,
            "Win Rate": 0.6
        }
        result = _pick_metric(stats, ["Sharpe Ratio"])
        assert result == 1.5

    def test_order_matters_with_multiple_matches(self):
        """Should respect candidate order when multiple could match."""
        stats = {
            "Sharpe Ratio (252 days)": 1.8,
            "Sharpe Ratio": 1.5,
            "Sharpe": 2.0
        }
        result = _pick_metric(stats, ["Sharpe Ratio", "Sharpe Ratio (252 days)"])
        assert result == 1.5


class TestExtractTimestampedSeriesFromAccount:
    """Test suite for _extract_timestamped_series_from_account function."""

    def test_named_index_ts_event(self):
        """Should handle DataFrame with 'ts_event' named index."""
        df = pd.DataFrame(
            {"total": [100.0, 110.0, 105.0]},
            index=pd.DatetimeIndex(
                ["2024-01-01", "2024-01-02", "2024-01-03"], name="ts_event"
            )
        )
        result = _extract_timestamped_series_from_account(df, "total")
        
        assert list(result.columns) == ["timestamp", "total"]
        assert len(result) == 3
        assert result["total"].tolist() == [100.0, 110.0, 105.0]

    def test_unnamed_index(self):
        """Should handle DataFrame with unnamed index."""
        df = pd.DataFrame(
            {"balance": [100.0, 110.0, 105.0]},
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02", "2024-01-03"])
        )
        result = _extract_timestamped_series_from_account(df, "balance")
        
        assert list(result.columns) == ["timestamp", "balance"]
        assert len(result) == 3
        assert result["balance"].tolist() == [100.0, 110.0, 105.0]

    def test_already_named_timestamp(self):
        """Should handle DataFrame with index already named 'timestamp'."""
        df = pd.DataFrame(
            {"equity": [100.0, 110.0, 105.0]},
            index=pd.DatetimeIndex(
                ["2024-01-01", "2024-01-02", "2024-01-03"], name="timestamp"
            )
        )
        result = _extract_timestamped_series_from_account(df, "equity")
        
        assert list(result.columns) == ["timestamp", "equity"]
        assert len(result) == 3

    def test_missing_value_column(self):
        """Should return empty DataFrame when value column is missing."""
        df = pd.DataFrame(
            {"other_column": [100.0, 110.0]},
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="ts_event")
        )
        result = _extract_timestamped_series_from_account(df, "missing_column")
        
        assert list(result.columns) == ["timestamp", "missing_column"]
        assert len(result) == 0

    def test_proper_sorting(self):
        """Should sort by timestamp."""
        df = pd.DataFrame(
            {"total": [110.0, 100.0, 105.0]},
            index=pd.DatetimeIndex(
                ["2024-01-02", "2024-01-01", "2024-01-03"], name="ts_event"
            )
        )
        result = _extract_timestamped_series_from_account(df, "total")
        
        # Should be sorted by timestamp
        assert result["total"].tolist() == [100.0, 110.0, 105.0]

    def test_column_selection(self):
        """Should only include timestamp and value columns."""
        df = pd.DataFrame(
            {"total": [100.0, 110.0], "free": [50.0, 60.0], "locked": [50.0, 50.0]},
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="ts_event")
        )
        result = _extract_timestamped_series_from_account(df, "total")
        
        assert list(result.columns) == ["timestamp", "total"]
        assert "free" not in result.columns
        assert "locked" not in result.columns

    def test_reset_index_removes_original(self):
        """Should reset index and not carry over original index."""
        df = pd.DataFrame(
            {"balance": [100.0, 110.0]},
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="ts_event")
        )
        result = _extract_timestamped_series_from_account(df, "balance")
        
        # Index should be default integer index after reset
        assert result.index.tolist() == [0, 1]

    def test_custom_timestamp_column_name(self):
        """Should accept custom timestamp column name."""
        df = pd.DataFrame(
            {"total": [100.0, 110.0]},
            index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="ts_event")
        )
        result = _extract_timestamped_series_from_account(
            df, "total", ts_col_name="custom_time"
        )
        
        assert list(result.columns) == ["custom_time", "total"]

    def test_empty_dataframe(self):
        """Should handle empty DataFrame."""
        df = pd.DataFrame(columns=["total"])
        result = _extract_timestamped_series_from_account(df, "total")
        
        assert list(result.columns) == ["timestamp", "total"]
        assert len(result) == 0

    def test_values_preserved_correctly(self):
        """Should preserve exact values from the value column."""
        df = pd.DataFrame(
            {"total": [100.0, 110.5, 105.25, 120.75]},
            index=pd.DatetimeIndex(
                ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
                name="ts_event"
            )
        )
        result = _extract_timestamped_series_from_account(df, "total")
        
        assert result["total"].tolist() == [100.0, 110.5, 105.25, 120.75]

    def test_timestamps_preserved_correctly(self):
        """Should preserve exact timestamp values."""
        timestamps = pd.DatetimeIndex(
            ["2024-01-01 10:00:00", "2024-01-02 11:30:00", "2024-01-03 09:15:00"],
            name="ts_event"
        )
        df = pd.DataFrame({"balance": [100.0, 110.0, 105.0]}, index=timestamps)
        result = _extract_timestamped_series_from_account(df, "balance")
        
        # Convert to datetime for comparison
        result_timestamps = pd.to_datetime(result["timestamp"])
        assert result_timestamps.tolist() == timestamps.tolist()

    def test_multiple_columns_extracts_correct_one(self):
        """Should extract only the specified value column when multiple exist."""
        df = pd.DataFrame(
            {
                "total": [100.0, 110.0, 120.0],
                "free": [50.0, 60.0, 70.0],
                "locked": [50.0, 50.0, 50.0],
                "margin": [10.0, 15.0, 20.0]
            },
            index=pd.DatetimeIndex(
                ["2024-01-01", "2024-01-02", "2024-01-03"], name="ts_event"
            )
        )
        
        # Extract 'free' column
        result = _extract_timestamped_series_from_account(df, "free")
        assert result["free"].tolist() == [50.0, 60.0, 70.0]
        assert "total" not in result.columns
        assert "locked" not in result.columns
        
        # Extract 'locked' column
        result2 = _extract_timestamped_series_from_account(df, "locked")
        assert result2["locked"].tolist() == [50.0, 50.0, 50.0]
        assert "free" not in result2.columns

    def test_data_integrity_with_unsorted_input(self):
        """Should maintain data integrity when sorting unsorted timestamps."""
        df = pd.DataFrame(
            {"balance": [110.0, 100.0, 120.0, 105.0]},
            index=pd.DatetimeIndex(
                ["2024-01-02", "2024-01-01", "2024-01-04", "2024-01-03"],
                name="ts_event"
            )
        )
        result = _extract_timestamped_series_from_account(df, "balance")
        
        # After sorting, should be in correct order with matching values
        expected_order = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
        expected_values = [100.0, 110.0, 105.0, 120.0]
        
        result_dates = pd.to_datetime(result["timestamp"]).dt.strftime("%Y-%m-%d").tolist()
        assert result_dates == expected_order
        assert result["balance"].tolist() == expected_values


class TestComputeTotalReturnAndMdd:
    """Test suite for _compute_total_return_and_mdd function."""

    # Total Return Tests
    def test_empty_dataframe(self):
        """Should return (0.0, 0.0) for empty DataFrame."""
        df = pd.DataFrame(columns=["timestamp", "equity_value"])
        total_return, max_drawdown = _compute_total_return_and_mdd(df)
        assert total_return == 0.0
        assert max_drawdown == 0.0

    def test_single_value(self):
        """Should return 0% return and 0% drawdown for single value."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01"],
            "equity_value": [100.0]
        })
        total_return, max_drawdown = _compute_total_return_and_mdd(df)
        assert total_return == 0.0
        assert max_drawdown == 0.0

    def test_positive_return_simple(self):
        """Should calculate positive return correctly: 100 -> 120 = 20%."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02"],
            "equity_value": [100.0, 120.0]
        })
        total_return, _ = _compute_total_return_and_mdd(df)
        assert total_return == pytest.approx(0.20, rel=1e-6)  # 20%

    def test_negative_return_simple(self):
        """Should calculate negative return correctly: 100 -> 80 = -20%."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02"],
            "equity_value": [100.0, 80.0]
        })
        total_return, _ = _compute_total_return_and_mdd(df)
        assert total_return == pytest.approx(-0.20, rel=1e-6)  # -20%

    def test_zero_initial_equity(self):
        """Should handle zero initial equity edge case."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02"],
            "equity_value": [0.0, 100.0]
        })
        total_return, _ = _compute_total_return_and_mdd(df)
        assert total_return == 0.0

    def test_100_percent_return(self):
        """Should calculate 100% return correctly: 100 -> 200."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02"],
            "equity_value": [100.0, 200.0]
        })
        total_return, _ = _compute_total_return_and_mdd(df)
        assert total_return == pytest.approx(1.0, rel=1e-6)  # 100%

    def test_total_return_uses_first_and_last_only(self):
        """Should calculate return from first to last value only."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "equity_value": [100.0, 150.0, 80.0, 110.0]
        })
        total_return, _ = _compute_total_return_and_mdd(df)
        # 100 -> 110 = 10%
        assert total_return == pytest.approx(0.10, rel=1e-6)

    # Max Drawdown Tests
    def test_no_drawdown_monotonic_increase(self):
        """Should return 0% drawdown for monotonically increasing equity."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "equity_value": [100.0, 110.0, 120.0, 130.0]
        })
        _, max_drawdown = _compute_total_return_and_mdd(df)
        assert max_drawdown == pytest.approx(0.0, rel=1e-6)

    def test_simple_drawdown(self):
        """Should calculate simple drawdown: 100 -> 120 -> 90 = -25% from peak."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "equity_value": [100.0, 120.0, 90.0]
        })
        _, max_drawdown = _compute_total_return_and_mdd(df)
        # Peak at 120, drops to 90: (90/120) - 1 = -0.25 = -25%
        assert max_drawdown == pytest.approx(-0.25, rel=1e-6)

    def test_multiple_drawdowns_picks_maximum(self):
        """Should pick the maximum (worst) drawdown among multiple."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "equity_value": [100.0, 120.0, 110.0, 150.0, 120.0]  
        })
        _, max_drawdown = _compute_total_return_and_mdd(df)
        # First DD: 120 -> 110 = -8.33%
        # Second DD: 150 -> 120 = -20%
        # Max is -20%
        assert max_drawdown == pytest.approx(-0.20, rel=1e-6)

    def test_drawdown_with_recovery(self):
        """Should calculate MDD even after recovery: 100 -> 120 -> 90 -> 130."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "equity_value": [100.0, 120.0, 90.0, 130.0]
        })
        _, max_drawdown = _compute_total_return_and_mdd(df)
        # Peak at 120, drops to 90: -25%
        # Even though it recovers to 130, MDD is still -25%
        assert max_drawdown == pytest.approx(-0.25, rel=1e-6)

    def test_continuous_decline(self):
        """Should calculate MDD for continuous decline: 100 -> 90 -> 80 -> 70."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "equity_value": [100.0, 90.0, 80.0, 70.0]
        })
        _, max_drawdown = _compute_total_return_and_mdd(df)
        # Peak at 100, drops to 70: (70/100) - 1 = -0.30 = -30%
        assert max_drawdown == pytest.approx(-0.30, rel=1e-6)

    def test_v_shaped_recovery(self):
        """Should calculate MDD for V-shaped pattern: 100 -> 50 -> 100."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "equity_value": [100.0, 50.0, 100.0]
        })
        _, max_drawdown = _compute_total_return_and_mdd(df)
        # Peak at 100, drops to 50: -50%
        assert max_drawdown == pytest.approx(-0.50, rel=1e-6)

    # Combined Tests
    def test_positive_return_with_drawdown(self):
        """Should handle positive return with significant drawdown independently."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "equity_value": [100.0, 150.0, 90.0, 120.0]
        })
        total_return, max_drawdown = _compute_total_return_and_mdd(df)
        # Return: 100 -> 120 = 20%
        # MDD: 150 -> 90 = -40%
        assert total_return == pytest.approx(0.20, rel=1e-6)
        assert max_drawdown == pytest.approx(-0.40, rel=1e-6)

    def test_negative_return_with_multiple_drawdowns(self):
        """Should handle negative return with multiple drawdowns."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "equity_value": [100.0, 120.0, 80.0, 90.0]
        })
        total_return, max_drawdown = _compute_total_return_and_mdd(df)
        # Return: 100 -> 90 = -10%
        # MDD: 120 -> 80 = -33.33%
        assert total_return == pytest.approx(-0.10, rel=1e-6)
        assert max_drawdown == pytest.approx(-1/3, rel=1e-6)


class TestComputeUnrealizedSeriesFromReports:
    """Test suite for compute_unrealized_series_from_reports function."""

    def test_empty_equity_curve(self):
        """Should return empty DataFrame with correct columns for empty equity curve."""
        equity_curve = pd.DataFrame(columns=["timestamp", "equity_value"])
        positions_df = pd.DataFrame(columns=["ts_closed", "realized_pnl"])
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        assert list(result.columns) == ["timestamp", "unrealized_pnl"]
        assert len(result) == 0

    def test_none_equity_curve(self):
        """Should return empty DataFrame when equity_curve is None."""
        result = compute_unrealized_series_from_reports(None, None)
        
        assert list(result.columns) == ["timestamp", "unrealized_pnl"]
        assert len(result) == 0

    def test_no_realized_positions_empty_df(self):
        """Should compute unrealized = equity - initial when positions_df is empty."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "equity_value": [100.0, 110.0, 120.0]
        })
        positions_df = pd.DataFrame(columns=["ts_closed", "realized_pnl"])
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # unrealized = equity - initial_equity (100)
        expected = [0.0, 10.0, 20.0]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)

    def test_no_realized_positions_none(self):
        """Should compute unrealized = equity - initial when positions_df is None."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "equity_value": [100.0, 110.0, 105.0]
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, None)
        
        # unrealized = equity - initial_equity (100)
        expected = [0.0, 10.0, 5.0]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)

    def test_missing_required_columns(self):
        """Should fallback when positions_df missing ts_closed or realized_pnl columns."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "equity_value": [100.0, 110.0]
        })
        positions_df = pd.DataFrame({"other_column": [1, 2]})
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # Should fallback to: unrealized = equity - initial
        expected = [0.0, 10.0]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)

    def test_accounting_identity_simple(self):
        """Should verify accounting identity: unrealized = equity - equity0 - cum_realized."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01 10:00", "2024-01-01 11:00", 
                                        "2024-01-01 12:00", "2024-01-01 13:00"]),
            "equity_value": [100.0, 110.0, 105.0, 115.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-01 11:30", "2024-01-01 13:30"]),
            "realized_pnl": [10.0, 5.0]
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # Manual calculation:
        # t1 (10:00): 100 - 100 - 0 = 0
        # t2 (11:00): 110 - 100 - 0 = 10 (realized event at 11:30 hasn't happened yet)
        # t3 (12:00): 105 - 100 - 10 = -5 (after 11:30 realization of +10)
        # t4 (13:00): 115 - 100 - 10 = 5 (before 13:30 realization)
        expected = [0.0, 10.0, -5.0, 5.0]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)

    def test_accounting_identity_with_negative_realized(self):
        """Should handle negative realized PnL correctly."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "equity_value": [100.0, 95.0, 90.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-01 12:00", "2024-01-02 12:00"]),
            "realized_pnl": [-5.0, -3.0]
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # t1: 100 - 100 - 0 = 0 (before any realization)
        # t2: 95 - 100 - (-5) = 0 (after -5 realized)
        # t3: 90 - 100 - (-8) = -2 (after cumulative -8 realized)
        expected = [0.0, 0.0, -2.0]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)

    def test_formatted_realized_pnl_strings(self):
        """Should parse formatted realized_pnl strings using _parse_money_to_float."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "equity_value": [100.0, 110.0, 115.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-01 12:00", "2024-01-02 12:00"]),
            "realized_pnl": ["USD 10.50", "-5.25"]  # Formatted strings
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # t1: 100 - 100 - 0 = 0
        # t2: 110 - 100 - 10.5 = -0.5
        # t3: 115 - 100 - 5.25 = 9.75 (cum_realized = 10.5 - 5.25 = 5.25)
        expected = [0.0, -0.5, 9.75]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)

    def test_null_realized_pnl_fillna(self):
        """Should handle null/NaN realized_pnl values by filling with 0."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "equity_value": [100.0, 110.0, 120.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-01 12:00", "2024-01-02 12:00"]),
            "realized_pnl": [10.0, None]  # Second value is None
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # t1: 100 - 100 - 0 = 0
        # t2: 110 - 100 - 10 = 0
        # t3: 120 - 100 - 10 = 10 (None treated as 0)
        expected = [0.0, 0.0, 10.0]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)

    def test_timestamp_alignment_merge_asof(self):
        """Should align realized events to equity timestamps correctly using merge_asof."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01 09:00", "2024-01-01 10:00", 
                                        "2024-01-01 11:00", "2024-01-01 12:00"]),
            "equity_value": [100.0, 105.0, 110.0, 115.0]
        })
        # Realized event happens between equity timestamps
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-01 09:30", "2024-01-01 11:30"]),
            "realized_pnl": [5.0, 3.0]
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # 09:00: 100 - 100 - 0 = 0 (before 09:30 realization)
        # 10:00: 105 - 100 - 5 = 0 (after 09:30 realization)
        # 11:00: 110 - 100 - 5 = 5 (before 11:30 realization)
        # 12:00: 115 - 100 - 8 = 7 (after 11:30 realization, cum = 5+3 = 8)
        expected = [0.0, 0.0, 5.0, 7.0]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)

    def test_unsorted_timestamps(self):
        """Should handle unsorted timestamps correctly."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-02", "2024-01-01", "2024-01-03"]),
            "equity_value": [110.0, 100.0, 115.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-02 12:00"]),
            "realized_pnl": [8.0]
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # After sorting:
        # 2024-01-01: 100 - 100 - 0 = 0
        # 2024-01-02: 110 - 100 - 0 = 10 (assuming realization is after this timestamp)
        # 2024-01-03: 115 - 100 - 8 = 7
        # Note: merge_asof with direction='backward' means we use last known cum_realized
        assert len(result) == 3
        assert result["unrealized_pnl"].iloc[0] == pytest.approx(0.0)

    def test_multiple_realizations_same_timestamp(self):
        """Should handle multiple realizations at the same timestamp."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "equity_value": [100.0, 110.0, 120.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": pd.to_datetime(["2024-01-01 12:00", "2024-01-01 12:00", "2024-01-02 12:00"]),
            "realized_pnl": [5.0, 3.0, 7.0]
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # Cumulative realized should sum all events
        # t1: 100 - 100 - 0 = 0
        # t2: 110 - 100 - 8 = 2 (cum = 5+3 = 8)
        # t3: 120 - 100 - 15 = 5 (cum = 5+3+7 = 15)
        expected = [0.0, 2.0, 5.0]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)

    def test_only_open_positions_no_ts_closed(self):
        """Should handle positions with null ts_closed (open positions)."""
        equity_curve = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "equity_value": [100.0, 110.0]
        })
        positions_df = pd.DataFrame({
            "ts_closed": [None, pd.Timestamp("2024-01-01 12:00")],
            "realized_pnl": [0.0, 5.0]
        })
        
        result = compute_unrealized_series_from_reports(equity_curve, positions_df)
        
        # Only closed positions should be used (second row)
        # t1: 100 - 100 - 0 = 0
        # t2: 110 - 100 - 5 = 5
        expected = [0.0, 5.0]
        assert result["unrealized_pnl"].tolist() == pytest.approx(expected)


