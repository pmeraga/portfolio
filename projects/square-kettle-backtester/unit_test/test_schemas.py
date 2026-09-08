"""
Unit tests for data validation functions in schemas.py.

Tests data quality checks, validation logic, and edge cases.
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

from data.schemas import (
    validate_quotes_df,
    validate_trades_df,
    validate_bars_df,
    coerce_dtypes_quotes,
    coerce_dtypes_trades,
    coerce_dtypes_bars,
)


class TestValidateQuotesDf:
    """Test suite for validate_quotes_df function."""

    def test_valid_quotes_no_filtering(self):
        """Should pass validation for normal quotes."""
        df = pd.DataFrame({
            "ts_event_ns": [1000000000, 2000000000],
            "ts_recv_ns": [1000000001, 2000000001],
            "instrument_id": ["ES.n.0.GLBX", "ES.n.0.GLBX"],
            "symbol": ["ES", "ES"],
            "bid_price": [4500.0, 4501.0],
            "bid_size": [10.0, 15.0],
            "ask_price": [4500.25, 4501.25],
            "ask_size": [12.0, 18.0],
            "spread": [0.25, 0.25],
            "mid": [4500.125, 4501.125],
            "source": ["tbbo", "tbbo"]
        })
        result = validate_quotes_df(df, filter_crossed_quotes=True)
        assert len(result) == 2
        assert result.equals(df)

    def test_crossed_quotes_filtered_by_default(self):
        """Should filter crossed quotes (bid > ask) by default."""
        df = pd.DataFrame({
            "ts_event_ns": [1000000000, 2000000000, 3000000000],
            "ts_recv_ns": [1000000001, 2000000001, 3000000001],
            "instrument_id": ["ES.n.0.GLBX"] * 3,
            "symbol": ["ES"] * 3,
            "bid_price": [4500.0, 4501.0, 4502.0],  # Third one is crossed
            "bid_size": [10.0, 15.0, 20.0],
            "ask_price": [4500.25, 4501.25, 4500.5],  # 4502.0 > 4500.5
            "ask_size": [12.0, 18.0, 22.0],
            "spread": [0.25, 0.25, -1.5],  # Negative spread indicates crossed
            "mid": [4500.125, 4501.125, 4501.25],
            "source": ["tbbo"] * 3
        })
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = validate_quotes_df(df, filter_crossed_quotes=True)
            
            # Should have filtered out 1 crossed quote
            assert len(result) == 2
            assert len(w) == 1
            assert "Filtered" in str(w[0].message)
            assert "crossed quotes" in str(w[0].message).lower()
            
            # Remaining quotes should be valid
            assert (result["bid_price"] <= result["ask_price"]).all()

    def test_crossed_quotes_kept_when_filter_false(self):
        """Should keep crossed quotes when filter_crossed_quotes=False."""
        df = pd.DataFrame({
            "ts_event_ns": [1000000000, 2000000000],
            "ts_recv_ns": [1000000001, 2000000001],
            "instrument_id": ["ES.n.0.GLBX"] * 2,
            "symbol": ["ES"] * 2,
            "bid_price": [4500.0, 4502.0],  # Second is crossed
            "bid_size": [10.0, 20.0],
            "ask_price": [4500.25, 4500.5],  # 4502.0 > 4500.5
            "ask_size": [12.0, 22.0],
            "spread": [0.25, -1.5],
            "mid": [4500.125, 4501.25],
            "source": ["tbbo"] * 2
        })
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = validate_quotes_df(df, filter_crossed_quotes=False)
            
            # Should keep all quotes
            assert len(result) == 2
            assert len(w) == 1
            assert "Detected" in str(w[0].message)
            assert "kept for traceability" in str(w[0].message).lower()

    def test_negative_sizes_raise_error(self):
        """Should raise ValueError for negative bid/ask sizes."""
        df = pd.DataFrame({
            "ts_event_ns": [1000000000],
            "ts_recv_ns": [1000000001],
            "instrument_id": ["ES.n.0.GLBX"],
            "symbol": ["ES"],
            "bid_price": [4500.0],
            "bid_size": [-10.0],  # Negative size
            "ask_price": [4500.25],
            "ask_size": [12.0],
            "spread": [0.25],
            "mid": [4500.125],
            "source": ["tbbo"]
        })
        
        with pytest.raises(ValueError, match="negative sizes"):
            validate_quotes_df(df)

    def test_empty_dataframe(self):
        """Should handle empty DataFrame."""
        df = pd.DataFrame(columns=[
            "ts_event_ns", "ts_recv_ns", "instrument_id", "symbol",
            "bid_price", "bid_size", "ask_price", "ask_size",
            "spread", "mid", "source"
        ])
        result = validate_quotes_df(df)
        assert len(result) == 0
        assert list(result.columns) == list(df.columns)


class TestValidateTradesDf:
    """Test suite for validate_trades_df function."""

    def test_valid_trades(self):
        """Should pass validation for normal trades."""
        df = pd.DataFrame({
            "ts_event_ns": [1000000000, 2000000000],
            "ts_recv_ns": [1000000001, 2000000001],
            "instrument_id": ["ES.n.0.GLBX", "ES.n.0.GLBX"],
            "symbol": ["ES", "ES"],
            "price": [4500.0, 4501.0],
            "size": [5.0, 10.0],
            "dataset": ["GLBX.MDP3", "GLBX.MDP3"]
        })
        result = validate_trades_df(df)
        assert len(result) == 2

    def test_non_positive_price_raises_error(self):
        """Should raise ValueError for non-positive prices."""
        df = pd.DataFrame({
            "ts_event_ns": [1000000000],
            "ts_recv_ns": [1000000001],
            "instrument_id": ["ES.n.0.GLBX"],
            "symbol": ["ES"],
            "price": [0.0],  # Zero price
            "size": [5.0],
            "dataset": ["GLBX.MDP3"]
        })
        
        with pytest.raises(ValueError, match="non-positive price"):
            validate_trades_df(df)

    def test_negative_size_raises_error(self):
        """Should raise ValueError for negative trade sizes."""
        df = pd.DataFrame({
            "ts_event_ns": [1000000000],
            "ts_recv_ns": [1000000001],
            "instrument_id": ["ES.n.0.GLBX"],
            "symbol": ["ES"],
            "price": [4500.0],
            "size": [-5.0],  # Negative size
            "dataset": ["GLBX.MDP3"]
        })
        
        with pytest.raises(ValueError, match="negative size"):
            validate_trades_df(df)


class TestValidateBarsDf:
    """Test suite for validate_bars_df function."""

    def test_valid_bars(self):
        """Should pass validation for normal bars."""
        df = pd.DataFrame({
            "ts_start_ns": [1000000000, 2000000000],
            "ts_end_ns": [1060000000, 2060000000],
            "instrument_id": ["ES.n.0.GLBX", "ES.n.0.GLBX"],
            "symbol": ["ES", "ES"],
            "open": [4500.0, 4501.0],
            "high": [4502.0, 4503.0],
            "low": [4499.0, 4500.0],
            "close": [4501.0, 4502.0],
            "volume": [100.0, 150.0],
            "bar_span_s": [60, 60],
            "dataset": ["GLBX.MDP3", "GLBX.MDP3"]
        })
        result = validate_bars_df(df)
        assert len(result) == 2

    def test_high_less_than_low_raises_error(self):
        """Should raise ValueError when high < low."""
        df = pd.DataFrame({
            "ts_start_ns": [1000000000],
            "ts_end_ns": [1060000000],
            "instrument_id": ["ES.n.0.GLBX"],
            "symbol": ["ES"],
            "open": [4500.0],
            "high": [4499.0],  # High < low
            "low": [4500.0],
            "close": [4501.0],
            "volume": [100.0],
            "bar_span_s": [60],
            "dataset": ["GLBX.MDP3"]
        })
        
        with pytest.raises(ValueError, match="high < low"):
            validate_bars_df(df)

    def test_negative_volume_raises_error(self):
        """Should raise ValueError for negative volume."""
        df = pd.DataFrame({
            "ts_start_ns": [1000000000],
            "ts_end_ns": [1060000000],
            "instrument_id": ["ES.n.0.GLBX"],
            "symbol": ["ES"],
            "open": [4500.0],
            "high": [4502.0],
            "low": [4499.0],
            "close": [4501.0],
            "volume": [-100.0],  # Negative volume
            "bar_span_s": [60],
            "dataset": ["GLBX.MDP3"]
        })
        
        with pytest.raises(ValueError, match="negative volume"):
            validate_bars_df(df)


class TestCoerceDtypes:
    """Test suite for dtype coercion functions."""

    def test_coerce_quotes_dtypes(self):
        """Should coerce quotes DataFrame to correct dtypes."""
        df = pd.DataFrame({
            "ts_event_ns": ["1000000000", "2000000000"],  # String
            "ts_recv_ns": ["1000000001", "2000000001"],
            "instrument_id": ["ES.n.0.GLBX", "ES.n.0.GLBX"],
            "symbol": ["ES", "ES"],
            "bid_price": ["4500.0", "4501.0"],  # String
            "bid_size": ["10.0", "15.0"],
            "ask_price": ["4500.25", "4501.25"],
            "ask_size": ["12.0", "18.0"],
        })
        
        result = coerce_dtypes_quotes(df)
        
        # Check that types are correct
        assert result["ts_event_ns"].dtype == "int64"
        assert result["bid_price"].dtype == "float64"
        assert result["bid_size"].dtype == "float64"
        assert "spread" in result.columns
        assert "mid" in result.columns

    def test_coerce_trades_dtypes(self):
        """Should coerce trades DataFrame to correct dtypes."""
        df = pd.DataFrame({
            "ts_event_ns": ["1000000000"],
            "ts_recv_ns": ["1000000001"],
            "instrument_id": ["ES.n.0.GLBX"],
            "symbol": ["ES"],
            "price": ["4500.0"],  # String
            "size": ["5.0"],
            "dataset": ["GLBX.MDP3"]
        })
        
        result = coerce_dtypes_trades(df)
        
        assert result["ts_event_ns"].dtype == "int64"
        assert result["price"].dtype == "float64"
        assert result["size"].dtype == "float64"

    def test_coerce_bars_dtypes(self):
        """Should coerce bars DataFrame to correct dtypes."""
        df = pd.DataFrame({
            "ts_start_ns": ["1000000000"],
            "ts_end_ns": ["1060000000"],
            "instrument_id": ["ES.n.0.GLBX"],
            "symbol": ["ES"],
            "open": ["4500.0"],  # String
            "high": ["4502.0"],
            "low": ["4499.0"],
            "close": ["4501.0"],
            "volume": ["100.0"],
            "bar_span_s": ["60"],
            "dataset": ["GLBX.MDP3"]
        })
        
        result = coerce_dtypes_bars(df)
        
        assert result["ts_start_ns"].dtype == "int64"
        assert result["open"].dtype == "float64"
        assert result["volume"].dtype == "float64"

