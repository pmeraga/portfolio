# src/data/schemas.py
from __future__ import annotations
"""
Schema constants, dtypes, and validators for interim CSVs (strategy-agnostic).

This module provides:
- Data type definitions for trades, quotes, and bars
- Validation functions to ensure data quality
- Data coercion functions to normalize data types
- BacktestResult class for standardized backtest output

All timestamps are int64 nanoseconds UTC. Sizes/quantities are float64.

Key Functions:
    - validate_trades_df: Validates and filters trade data
    - validate_quotes_df: Validates and optionally filters crossed quotes
    - validate_bars_df: Validates OHLCV bar data
    - coerce_dtypes_*: Normalize data types for consistency
    - enrich_quotes: Add computed fields (spread, mid price)

Data Quality:
    - Crossed quotes (bid > ask) are filtered by default to prevent incorrect execution prices
    - Negative sizes/volumes raise errors
    - Invalid price relationships are detected and handled
"""

from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np
import json
from pathlib import Path
from collections.abc import Mapping, Sequence
import warnings

ALLOWED_SCHEMAS = {
    # OHLCV bars
    "ohlcv-1s", "ohlcv-1m", "ohlcv-1h", "ohlcv-1d",

    # tick-level top of book & trades
    "tbbo", "tcbbo", "trades",

    # book depth
    "mbp-1", "mbp-10", "mbo", "cmbp-1",

    # aggregated BBO bars
    "bbo-1s", "bbo-1m", "cbbo-1s", "cbbo-1m",
}

DEFAULT_BAR_SPANS = {
    "ohlcv-1s": 1,
    "ohlcv-1m": 60,
    "ohlcv-1h": 3600,
    "ohlcv-1d": 86400,
}

DTYPES_TRADES: Dict[str, str] = {
    "ts_event_ns": "int64",
    "ts_recv_ns": "int64",
    "instrument_id": "string",
    "symbol": "string",
    "price": "float64",
    "size": "float64",
    "dataset": "string",
}

DTYPES_QUOTES: Dict[str, str] = {
    "ts_event_ns": "int64",
    "ts_recv_ns": "int64",
    "instrument_id": "string",
    "symbol": "string",
    "bid_price": "float64",
    "bid_size": "float64",
    "ask_price": "float64",
    "ask_size": "float64",
    "spread": "float64",  # computed
    "mid": "float64",     # computed
    "source": "string",   # e.g., tbbo/tcbbo
}

DTYPES_BARS: Dict[str, str] = {
    "ts_start_ns": "int64",
    "ts_end_ns": "int64",
    "instrument_id": "string",
    "symbol": "string",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "float64",
    "bar_span_s": "int64",
    "dataset": "string",
}

REQUIRED_TRADES = list(DTYPES_TRADES.keys())
REQUIRED_QUOTES = list(DTYPES_QUOTES.keys())
REQUIRED_BARS = list(DTYPES_BARS.keys())


def _require_cols(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")


def coerce_dtypes_trades(df: pd.DataFrame) -> pd.DataFrame:
    _require_cols(df, REQUIRED_TRADES, "trades")
    return df.astype(DTYPES_TRADES)


def coerce_dtypes_quotes(df: pd.DataFrame) -> pd.DataFrame:
    if "spread" not in df.columns:
        df["spread"] = df["ask_price"] - df["bid_price"]
    if "mid" not in df.columns:
        df["mid"] = (df["ask_price"] + df["bid_price"]) / 2.0
    if "source" not in df.columns:
        df["source"] = pd.Series(["unknown"] * len(df), dtype="string")
    _require_cols(df, REQUIRED_QUOTES, "quotes")
    return df.astype(DTYPES_QUOTES)


def coerce_dtypes_bars(df: pd.DataFrame) -> pd.DataFrame:
    _require_cols(df, REQUIRED_BARS, "bars")
    return df.astype(DTYPES_BARS)


def validate_trades_df(df: pd.DataFrame) -> pd.DataFrame:
    df = coerce_dtypes_trades(df)
    if (df["price"] <= 0).any():
        raise ValueError("trades: non-positive price detected")
    if (df["size"] < 0).any():
        raise ValueError("trades: negative size detected")
    return df


def validate_quotes_df(df: pd.DataFrame, filter_crossed_quotes: bool = True) -> pd.DataFrame:
    """
    Validate quotes DataFrame and optionally filter invalid crossed quotes.
    
    Args:
        df: DataFrame with quote data
        filter_crossed_quotes: If True, remove rows where bid_price > ask_price.
                              If False, keep them but warn (for traceability).
    
    Returns:
        Validated (and optionally filtered) DataFrame
    """
    df = coerce_dtypes_quotes(df)
    
    # Check for crossed quotes (bid > ask) - invalid market data
    crossed_mask = df["bid_price"] > df["ask_price"]
    if crossed_mask.any():
        bad_rows = crossed_mask.sum()
        if filter_crossed_quotes:
            warnings.warn(
                f"[quotes] Filtered {bad_rows} crossed quotes (bid_price > ask_price). "
                f"This indicates data quality issues - using mid-price fallback for these timestamps.",
                category=UserWarning,
                stacklevel=2,
            )
            # Filter out crossed quotes to prevent incorrect execution prices
            df = df[~crossed_mask].copy()
        else:
            warnings.warn(
                f"[quotes] Detected {bad_rows} crossed quotes (bid_price > ask_price). "
                f"These rows will be kept for traceability — consider filtering before analysis.",
                category=UserWarning,
                stacklevel=2,
            )
        
    if (df[["bid_size", "ask_size"]] < 0).any().any():
        raise ValueError("quotes: negative sizes detected")
    return df


def validate_bars_df(df: pd.DataFrame) -> pd.DataFrame:
    df = coerce_dtypes_bars(df)
    if (df["high"] < df["low"]).any():
        raise ValueError("bars: high < low detected")
    if (df["volume"] < 0).any():
        raise ValueError("bars: negative volume detected")
    return df


def enrich_quotes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["spread"] = df["ask_price"] - df["bid_price"]
    df["mid"] = (df["ask_price"] + df["bid_price"]) / 2.0
    return df


@dataclass
class BacktestResult:
    """
    Custom data class to hold backtest results from Nautilus Trader.
    """
    # Portfolio performance
    equity_curve: pd.DataFrame  # timestamp, equity_value
    balance_history: pd.DataFrame  # timestamp, balance
    pnl_realized: pd.DataFrame  # timestamp, realized_pnl
    pnl_unrealized: pd.DataFrame  # timestamp, unrealized_pnl
    
    # Trade data
    trades: pd.DataFrame  # All executed trades with entry/exit info
    positions: pd.DataFrame  # Position events (opened/closed)
    orders: pd.DataFrame  # Order fill events

    # Performance metrics
    total_return: float
    sharpe_ratio: Optional[float]
    max_drawdown: float
    win_rate: float
    profit_factor: Optional[float]
    
    # Metadata
    start_time: datetime
    end_time: datetime
    strategy_name: str
    instruments: list[str]
    
    # Custom data
    custom_indicators: Optional[dict[str, pd.DataFrame]] = None
    
    # Raw Nautilus result (optional, for advanced analysis)
    nautilus_result: Optional[object] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'total_return': self.total_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'strategy_name': self.strategy_name,
            'instruments': self.instruments,
        }
    
    def summary(self) -> str:
        """Generate a summary string of key metrics."""
        sharpe_str = f"{self.sharpe_ratio:.2f}" if self.sharpe_ratio is not None else "N/A"
        return (
            f"Backtest Results for {self.strategy_name}\n"
            f"Period: {self.start_time} to {self.end_time}\n"
            f"Total Return: {self.total_return:.2%}\n"
            f"Sharpe Ratio: {sharpe_str}\n"
            f"Max Drawdown: {self.max_drawdown:.2%}\n"
            f"Win Rate: {self.win_rate:.2%}\n"
            f"Trades: {len(self.trades)}"
        )
    
    def save(self, format: str = "parquet", base_dir: str = "backtest_results") -> str:
        """
        Save BacktestResult to local storage.

        Args:
            format: Storage format - "parquet" (default) or "csv"
            base_dir: Base directory for saving results (default: "backtest_results")

        Returns:
            str: The folder name where results were saved

        Creates structure:
        {base_dir}/
        └── {strategy_name}_{start_date}_{start_time}/
            ├── metadata.json
            ├── equity_curve.parquet
            ├── balance_history.parquet
            ├── pnl_realized.parquet
            ├── pnl_unrealized.parquet
            ├── trades.parquet
            ├── positions.parquet
            └── orders.parquet
        """
        # Create meaningful folder name from metadata
        start_date = self.start_time.strftime("%Y-%m-%d")
        start_time = self.start_time.strftime("%H-%M-%S")

        # Clean strategy name for filesystem
        clean_strategy_name = "".join(c for c in self.strategy_name if c.isalnum() or c in ('-', '_'))

        folder_name = f"{clean_strategy_name}_{start_date}_{start_time}"

        # Create directory structure
        base_path = Path(base_dir)
        save_path = base_path / folder_name
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Save metadata as JSON (without DataFrames and nautilus_result)
        metadata = {
            'total_return': self.total_return,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'strategy_name': self.strategy_name,
            'instruments': self.instruments,
            'format': format,
            'folder_name': folder_name,
            'save_timestamp': datetime.now().isoformat()
        }
        
        with open(save_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Save DataFrames
        dataframes = {
            'equity_curve': self.equity_curve,
            'balance_history': self.balance_history,
            'pnl_realized': self.pnl_realized,
            'pnl_unrealized': self.pnl_unrealized,
            'trades': self.trades,
            'positions': self.positions,
            'orders': self.orders
        }
        
        def _sanitize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
            # Convert non-primitive/object-like columns (dicts, lists, custom objects) to JSON strings
            # Drop columns that are entirely empty objects (all None/NaN or empty dict/list)
            if df is None or df.empty:
                return df
            df_clean = df.copy()
            for col in list(df_clean.columns):
                series = df_clean[col]
                # Identify if column is object-like
                if series.dtype == 'object':
                    # If all values are None/NaN or empty containers, coerce to empty string
                    def _is_empty_container(v):
                        return (isinstance(v, Mapping) and len(v) == 0) or (isinstance(v, (list, tuple, set)) and len(v) == 0)

                    if series.map(lambda v: (v is None) or (pd.isna(v) if not isinstance(v, (Mapping, Sequence)) else False) or _is_empty_container(v)).all():
                        # Column has no meaningful content; drop it to avoid empty struct
                        df_clean = df_clean.drop(columns=[col])
                        continue

                    # Convert dicts/lists/tuples to JSON strings
                    def _to_json_safe(v):
                        if isinstance(v, (Mapping, list, tuple)):
                            try:
                                return json.dumps(v)
                            except Exception:
                                return str(v)
                        # Leave primitives as-is
                        return v

                    df_clean[col] = series.map(_to_json_safe)

                # Ensure pandas nullable string for obvious string columns
                if pd.api.types.is_string_dtype(df_clean[col]):
                    df_clean[col] = df_clean[col].astype('string')
            return df_clean

        for name, df in dataframes.items():
            if not df.empty:
                df_to_write = _sanitize_for_parquet(df)
                if format == "parquet":
                    df_to_write.to_parquet(save_path / f"{name}.parquet", index=False)
                elif format == "csv":
                    df_to_write.to_csv(save_path / f"{name}.csv", index=False)

        print(f"BacktestResult saved to {base_dir}/{folder_name} (format: {format})")
        return folder_name
    
    @classmethod
    def load(cls, folder_name: str, base_dir: str = "backtest_results") -> "BacktestResult":
        """
        Load BacktestResult from storage.

        Args:
            folder_name: Name of the folder containing saved results
            base_dir: Base directory where results are stored (default: "backtest_results")

        Returns:
            BacktestResult: Loaded backtest results

        Example:
            result = BacktestResult.load("MyStrategy_2025-09-17_14-30-45")
            result = BacktestResult.load("MyStrategy_2025-09-17_14-30-45", base_dir="sample_data/backtest_results")
        """
        # Construct path to saved results
        base_path = Path(base_dir)
        load_path = base_path / folder_name

        if not load_path.exists():
            raise FileNotFoundError(f"Folder {folder_name} not found in {base_dir} directory")
        
        # Load metadata
        metadata_file = load_path / "metadata.json"
        if not metadata_file.exists():
            raise FileNotFoundError(f"metadata.json not found in {folder_name}")
        
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
        
        # Determine format from metadata or guess
        format_type = metadata.get('format', 'parquet')
        
        # Load DataFrames
        dataframes = {}
        df_names = ['equity_curve', 'balance_history', 'pnl_realized', 'pnl_unrealized', 
                   'trades', 'positions', 'orders']
        
        for name in df_names:
            file_path = None
            if format_type == "parquet":
                file_path = load_path / f"{name}.parquet"
            elif format_type == "csv":
                file_path = load_path / f"{name}.csv"
            
            if file_path and file_path.exists():
                try:
                    if format_type == "parquet":
                        dataframes[name] = pd.read_parquet(file_path)
                    elif format_type == "csv":
                        dataframes[name] = pd.read_csv(file_path)
                        # Convert timestamp columns back to datetime
                        if 'timestamp' in dataframes[name].columns:
                            dataframes[name]['timestamp'] = pd.to_datetime(dataframes[name]['timestamp'])
                except Exception as e:
                    print(f"Warning: Could not load {name}: {e}")
                    dataframes[name] = pd.DataFrame()
            else:
                dataframes[name] = pd.DataFrame()
        
        # Keep trades in original Nautilus format (no conversion needed)
        trades_df = dataframes['trades']
        
        # Reconstruct BacktestResult
        result = cls(
            equity_curve=dataframes['equity_curve'],
            balance_history=dataframes['balance_history'],
            pnl_realized=dataframes['pnl_realized'],
            pnl_unrealized=dataframes['pnl_unrealized'],
            trades=trades_df,
            positions=dataframes['positions'],
            orders=dataframes['orders'],
            total_return=metadata['total_return'],
            sharpe_ratio=metadata['sharpe_ratio'],
            max_drawdown=metadata['max_drawdown'],
            win_rate=metadata['win_rate'],
            profit_factor=metadata['profit_factor'],
            start_time=datetime.fromisoformat(metadata['start_time']),
            end_time=datetime.fromisoformat(metadata['end_time']),
            strategy_name=metadata['strategy_name'],
            instruments=metadata['instruments'],
            nautilus_result=None  # Raw result not saved
        )

        print(f"BacktestResult loaded from {base_dir}/{folder_name}")
        return result
