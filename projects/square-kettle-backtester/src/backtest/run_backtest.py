"""
Backtest execution and result processing module.

This module provides high-level functions to run backtests using NautilusTrader
and convert the results into a standardized BacktestResult format.

Key Functions:
    - run_backtest: Main entry point for running backtests
    - compute_unrealized_series_from_reports: Calculate unrealized PnL from account data
    - _compute_total_return_and_mdd: Calculate performance metrics from equity curve

The module handles:
    - Multiple strategy execution
    - Data extraction from Nautilus engine reports
    - Performance metric calculation
    - Error handling and data validation
"""

from __future__ import annotations

from typing import Optional, List, Dict, Iterable, Tuple, Any

import re
import pandas as pd

from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import BacktestRunConfig
from nautilus_trader.model.identifiers import Venue

from data.schemas import BacktestResult

def _extract_timestamped_series_from_account(
    account_df: pd.DataFrame,
    value_col: str,
    ts_col_name: str = "timestamp",
) -> pd.DataFrame:
    """
    Convert the account report (index=ts_event) into a 2-column time series DataFrame.
    Handles cases where the index name may or may not be 'ts_event'.
    """
    if account_df.index.name is None:
        # Reset index gives 'index' column; rename to timestamp
        df = account_df.reset_index().rename(columns={"index": ts_col_name})
    elif account_df.index.name != ts_col_name:
        # e.g., index named 'ts_event' -> rename to 'timestamp'
        df = account_df.reset_index().rename(columns={account_df.index.name: ts_col_name})
    else:
        df = account_df.reset_index()

    if value_col not in df.columns:
        return pd.DataFrame(columns=[ts_col_name, value_col])

    # Ensure proper ordering and types
    return df[[ts_col_name, value_col]].sort_values(ts_col_name).reset_index(drop=True)


def _compute_total_return_and_mdd(equity_curve: pd.DataFrame) -> Tuple[float, float]:
    """
    Compute total return and max drawdown from an equity curve DataFrame with
    columns ['timestamp', 'equity_value'].
    """
    if equity_curve.empty:
        return 0.0, 0.0

    s = pd.Series(equity_curve["equity_value"].astype(float).values)
    total_return = float(s.iloc[-1] / s.iloc[0] - 1.0) if s.iloc[0] != 0.0 else 0.0

    # Max drawdown on equity value
    rolling_max = s.cummax()
    dd = (s / rolling_max) - 1.0
    max_drawdown = float(dd.min()) if len(dd) else 0.0
    return total_return, max_drawdown


def _pick_metric(stats: Dict[str, Any], candidates: Iterable[str]) -> Optional[float]:
    """
    Find a metric value from a dict using a list of candidate keys (case-insensitive).
    Returns the first match cast to float when possible.
    """
    lower_map = {k.lower(): k for k in stats.keys()}
    for cand in candidates:
        k = lower_map.get(cand.lower())
        if k is not None:
            try:
                return float(stats[k])
            except Exception:
                return stats[k]  # leave as-is if not float
    return None


def _parse_money_to_float(x: Any) -> Optional[float]:
    """Robustly parse numeric value from possible formatted strings or numeric types.

    Examples handled: numeric types, strings like '-123.45', 'USD 123.45', etc.
    Returns None when parsing fails.
    """

    if isinstance(x, str):
        m = re.search(r"(-?\d+(?:\.\d+)?)", x)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
    try:
        return float(x)
    except Exception:
        return None


def compute_unrealized_series_from_reports(equity_curve: pd.DataFrame, positions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute portfolio-level unrealized PnL time series using accounting identity.
    
    Uses the accounting identity: unrealized(t) = equity(t) - equity(0) - cum_realized(t)
    
    Args:
        equity_curve: DataFrame with columns ['timestamp', 'equity_value']
        positions_df: Positions report containing 'ts_closed' and 'realized_pnl'.
                     The 'realized_pnl' column may contain numeric values or formatted strings
                     (e.g., "USD 10.50", "-5.25") which will be parsed automatically.
    
    Returns:
        DataFrame with columns ['timestamp', 'unrealized_pnl'] containing the unrealized
        PnL time series. Returns empty DataFrame if equity_curve is None or empty.
    
    Note:
        This function handles missing data gracefully:
        - If positions_df is missing required columns, falls back to: unrealized = equity - initial_equity
        - If positions_df is empty, assumes no realized PnL
        - Parses formatted realized_pnl strings automatically
    """
    if equity_curve is None or equity_curve.empty:
        return pd.DataFrame(columns=["timestamp", "unrealized_pnl"])

    curve = equity_curve.copy()
    # Normalize timestamps and sort
    curve["timestamp"] = pd.to_datetime(curve["timestamp"], utc=True)
    curve = curve.sort_values("timestamp").reset_index(drop=True)

    initial_equity = float(curve["equity_value"].astype(float).iloc[0])

    # If there are no realized events available, unrealized = equity - initial_equity
    if positions_df is None or positions_df.empty or "ts_closed" not in positions_df.columns or "realized_pnl" not in positions_df.columns:
        curve["unrealized_pnl"] = curve["equity_value"].astype(float) - initial_equity
        return curve[["timestamp", "unrealized_pnl"]]

    realized = positions_df.loc[positions_df["ts_closed"].notna(), ["ts_closed", "realized_pnl"]].copy()
    realized = realized.rename(columns={"ts_closed": "timestamp"})
    realized["timestamp"] = pd.to_datetime(realized["timestamp"], utc=True)
    # Parse realized values robustly
    realized["realized_pnl_num"] = realized["realized_pnl"].map(_parse_money_to_float).fillna(0.0)
    realized = realized.sort_values("timestamp").reset_index(drop=True)

    # cumulative realized
    realized["cum_realized"] = realized["realized_pnl_num"].cumsum()

    # Align cumulative realized to equity timestamps (use last known realized at or before equity timestamp)
    aligned = pd.merge_asof(curve, realized[["timestamp", "cum_realized"]], on="timestamp", direction="backward")
    aligned["cum_realized"] = aligned["cum_realized"].fillna(0.0)

    aligned["unrealized_pnl"] = aligned["equity_value"].astype(float) - initial_equity - aligned["cum_realized"]
    return aligned[["timestamp", "unrealized_pnl"]]


def run_backtest(
    configs: Optional[List[BacktestRunConfig]] = None,
    node: Optional[BacktestNode] = None,
    account_venue_name: Optional[str] = None,
) -> Dict[str, BacktestResult]:
    """
    Run high-level backtests and convert outputs to BacktestResult.
    Exactly one of `configs` or `node` must be provided.
    
    Args:
        configs: List of backtest configurations
        node: Pre-configured BacktestNode
        account_venue_name: Venue name for account reports. If None, auto-detects from engine.
        
    Returns:
        Dict keyed by run identifier -> BacktestResult
    """
    if (configs is None) == (node is None):
        raise ValueError("Provide exactly one of `configs` or `node`.")

    # Construct and run the BacktestNode if configs are supplied (high-level API flow)
    if node is None:
        # runtime-assert that configs is provided (caller must supply exactly one of configs or node)
        assert configs is not None, "Provide `configs` when `node` is None"
        local_node = BacktestNode(configs=configs)
    else:
        local_node = node

    local_node.run()  # executes backtests and populates engines

    # Resolve engines to post-process; prefer known configs -> get_engine(id)
    engines = []
    if configs is not None:
        for cfg in configs:
            eng = local_node.get_engine(cfg.id)  # quickstart-style retrieval
            engines.append((str(cfg.id), eng))
    else:
        # Node was supplied by caller; use get_engines() if available
        if hasattr(local_node, "get_engines"):
            for eng in local_node.get_engines():
                run_key = getattr(getattr(eng, "trader", None), "id", None)
                run_key = str(getattr(run_key, "value", run_key)) if run_key is not None else "run"
                engines.append((run_key, eng))
        else:
            raise RuntimeError("BacktestNode provided without configs and no get_engines() available.")

    results: Dict[str, BacktestResult] = {}

    for run_key, engine in engines:
        # Auto-detect venue if not provided
        if account_venue_name is None:
            venues = engine.list_venues()
            if not venues:
                raise RuntimeError(f"No venues found in engine for run {run_key}")
            venue = venues[0]
            venue_name = venue.value
        else:
            venue_name = account_venue_name
            venue = Venue(venue_name)

        # 1) Reports (documented trader helpers)
        orders_df      = engine.trader.generate_orders_report()
        fills_df       = engine.trader.generate_fills_report()
        positions_df   = engine.trader.generate_positions_report()
        account_df     = engine.trader.generate_account_report(Venue(venue_name))

        # 2) Portfolio statistics (documented analyzer getters)
        stats_returns  = engine.portfolio.analyzer.get_performance_stats_returns()
        stats_general  = engine.portfolio.analyzer.get_performance_stats_general()
        stats_pnls     = engine.portfolio.analyzer.get_performance_stats_pnls()

        # 3) Map to BacktestResult schema
        # Equity curve: from account 'total'
        equity_curve = _extract_timestamped_series_from_account(
            account_df, value_col="total", ts_col_name="timestamp"
        ).rename(columns={"total": "equity_value"})

        # Balance history: from account 'free' (available balance)
        balance_history = _extract_timestamped_series_from_account(
            account_df, value_col="free", ts_col_name="timestamp"
        ).rename(columns={"free": "balance"})

        # Realized PnL: from positions report at close time
        if "ts_closed" in positions_df.columns and "realized_pnl" in positions_df.columns:
            pnl_realized = (
                positions_df.loc[positions_df["ts_closed"].notna(), ["ts_closed", "realized_pnl"]]
                .rename(columns={"ts_closed": "timestamp"})
                .sort_values("timestamp")
                .reset_index(drop=True)
            )
        else:
            pnl_realized = pd.DataFrame(columns=["timestamp", "realized_pnl"])

        # Unrealized PnL: derive using accounting identity (equity - equity0 - cum_realized)
        try:
            pnl_unrealized = compute_unrealized_series_from_reports(equity_curve, positions_df)
        except Exception as e:
            # Fallback to empty series if something unexpected happens during computation
            # Log the error for debugging but continue with empty DataFrame to allow backtest to complete
            import warnings
            warnings.warn(
                f"Failed to compute unrealized PnL series: {e}. "
                f"Using empty DataFrame as fallback. This may indicate data quality issues.",
                category=UserWarning,
                stacklevel=2
            )
            pnl_unrealized = pd.DataFrame(columns=["timestamp", "unrealized_pnl"])

        # Metrics: pull if present; otherwise derive from equity curve
        sharpe_ratio = _pick_metric(
            stats_returns,
            ["Sharpe Ratio (252 days)", "Sharpe Ratio", "Sharpe"],
        )
        profit_factor = _pick_metric(
            stats_returns,
            ["Profit Factor"],
        )
        win_rate = (
            _pick_metric(stats_pnls, ["Win Rate"])
            or _pick_metric(stats_general, ["Win Rate", "win_rate"])
            or 0.0
        )

        # Derive total_return and max_drawdown from equity curve if not provided by analyzer
        total_return, max_drawdown = _compute_total_return_and_mdd(equity_curve)

        # Metadata: derive from observed data to avoid coupling to config shapes
        if not equity_curve.empty:
            # Convert timestamps to Python datetime objects
            # Note: Python datetime doesn't support nanoseconds, so we suppress the warning
            # The nanosecond precision is preserved in the DataFrame timestamps themselves
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='.*Discarding nonzero nanoseconds.*', category=UserWarning)
                start_ts = pd.to_datetime(equity_curve["timestamp"].iloc[0], utc=True)
                end_ts = pd.to_datetime(equity_curve["timestamp"].iloc[-1], utc=True)
                start_time = start_ts.to_pydatetime()
                end_time = end_ts.to_pydatetime()
        else:
            # Fallback to now if account series is empty
            now = pd.Timestamp.utcnow().to_pydatetime()
            start_time = now
            end_time = now

        # Strategy name: prefer first observed strategy_id in orders/fills/positions
        strategy_name = None
        for df, col in ((orders_df, "strategy_id"), (fills_df, "strategy_id"), (positions_df, "strategy_id")):
            if col in df.columns and len(df) > 0:
                strategy_name = str(df[col].iloc[0])
                break
        if strategy_name is None:
            strategy_name = "Strategy"

        # Instruments: union from fills/positions/orders
        instruments: List[str] = []
        for df, col in ((fills_df, "instrument_id"), (positions_df, "instrument_id"), (orders_df, "instrument_id")):
            if col in df.columns and len(df) > 0:
                instruments.extend(list(df[col].astype(str).unique()))
        instruments = sorted(set(instruments))

        # Extract custom indicators from strategy instances if available
        custom_indicators = None
        try:
            # Try to get strategies from the engine's trader
            if hasattr(engine, 'trader') and hasattr(engine.trader, 'cache'):
                # Get all strategy instances from the cache
                strategies = engine.trader.cache.strategies() if hasattr(engine.trader.cache, 'strategies') else []
                if not strategies and hasattr(engine.trader, 'strategies'):
                    strategies = list(engine.trader.strategies().values()) if callable(engine.trader.strategies) else []
                
                # Collect custom indicators from all strategies
                all_indicators = {}
                for strategy in strategies:
                    # Check if strategy has custom_indicators attribute (dict of name -> list of {timestamp, value})
                    if hasattr(strategy, 'custom_indicators') and isinstance(strategy.custom_indicators, dict):
                        for indicator_name, indicator_data in strategy.custom_indicators.items():
                            if indicator_data and len(indicator_data) > 0:
                                # Convert list of dicts to DataFrame
                                df_indicator = pd.DataFrame(indicator_data)
                                if 'timestamp' in df_indicator.columns and 'value' in df_indicator.columns:
                                    # Ensure timestamp is datetime
                                    df_indicator['timestamp'] = pd.to_datetime(df_indicator['timestamp'])
                                    df_indicator = df_indicator.sort_values('timestamp').reset_index(drop=True)
                                    all_indicators[indicator_name] = df_indicator[['timestamp', 'value']]
                    
                    # Also check for legacy 'custom' attribute (list format)
                    elif hasattr(strategy, 'custom') and isinstance(strategy.custom, list) and len(strategy.custom) > 0:
                        # Legacy format: list of dicts with indicator data
                        for item in strategy.custom:
                            if isinstance(item, dict) and 'name' in item and 'data' in item:
                                indicator_name = item['name']
                                indicator_data = item['data']
                                if isinstance(indicator_data, list) and len(indicator_data) > 0:
                                    df_indicator = pd.DataFrame(indicator_data)
                                    if 'timestamp' in df_indicator.columns and 'value' in df_indicator.columns:
                                        df_indicator['timestamp'] = pd.to_datetime(df_indicator['timestamp'])
                                        df_indicator = df_indicator.sort_values('timestamp').reset_index(drop=True)
                                        all_indicators[indicator_name] = df_indicator[['timestamp', 'value']]
                
                if all_indicators:
                    custom_indicators = all_indicators
        except Exception as e:
            # If extraction fails, continue without custom indicators
            import warnings
            warnings.warn(
                f"Could not extract custom indicators from strategies: {e}. "
                f"Continuing without custom indicators.",
                category=UserWarning,
                stacklevel=2
            )

        results[run_key] = BacktestResult(
            equity_curve=equity_curve,
            balance_history=balance_history,
            pnl_realized=pnl_realized,
            pnl_unrealized=pnl_unrealized,
            trades=fills_df.copy(),
            positions=positions_df.copy(),
            orders=orders_df.copy(),
            total_return=float(total_return),
            sharpe_ratio=float(sharpe_ratio) if sharpe_ratio is not None else None,
            max_drawdown=float(max_drawdown),
            win_rate=float(win_rate) if win_rate is not None else 0.0,
            profit_factor=float(profit_factor) if profit_factor is not None else None,
            start_time=start_time,
            end_time=end_time,
            strategy_name=strategy_name,
            instruments=instruments,
            nautilus_result=local_node,
            custom_indicators=custom_indicators,
        )

    return results
