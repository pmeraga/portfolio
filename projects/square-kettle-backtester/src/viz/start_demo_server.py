#!/usr/bin/env python3
"""
Demo script to start the Flask backend server with sample backtest data.
This will serve the API endpoints that the React frontend needs.
"""

import os

from data.schemas import BacktestResult
from viz.lightweight_charts_visualizer import LightweightChartsVisualizer
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

def create_demo_data():
    """Create sample backtest data for the demo that matches Nautilus Trader format."""
    # Create minimal sample data
    start_time = datetime.now() - timedelta(days=30)
    end_time = datetime.now()
    
    # Generate sample equity curve
    dates = pd.date_range(start=start_time, end=end_time, freq='D')
    equity_values = 10000 + np.cumsum(np.random.normal(50, 200, len(dates)))
    equity_curve = pd.DataFrame({
        'timestamp': dates,
        'equity_value': equity_values
    })
    
    # Generate sample trades in Nautilus format (fills_df)
    trade_dates = np.random.choice(dates, size=10, replace=False)
    np.random.seed(42)  # For reproducible demo
    
    trades = pd.DataFrame({
        'ts_event': trade_dates,
        'ts_init': trade_dates, 
        'trade_id': [f'TRADE-{i:03d}' for i in range(10)],
        'order_id': [f'ORDER-{i:03d}' for i in range(10)],
        'strategy_id': ['MACDStrategy-000'] * 10,
        'instrument_id': ['EUR/USD.SIM'] * 10,
        'venue': ['SIM'] * 10,
        'account_id': ['SIM-001'] * 10,
        'order_side': np.random.choice(['BUY', 'SELL'], size=10),
        'last_qty': np.random.uniform(10000, 100000, size=10),  # Nautilus uses larger quantities
        'last_px': np.random.uniform(1.05, 1.25, size=10),  # EUR/USD typical range
        'commission': np.random.uniform(0.5, 5.0, size=10),
        'liquidity_side': np.random.choice(['TAKER', 'MAKER'], size=10),
    })
    
    # Generate sample positions in Nautilus format
    position_dates = np.random.choice(dates, size=6, replace=False)
    positions = pd.DataFrame({
        'position_id': [f'P-{i:03d}' for i in range(6)],
        'strategy_id': ['MACDStrategy-000'] * 6,
        'instrument_id': ['EUR/USD.SIM'] * 6,
        'account_id': ['SIM-001'] * 6,
        'ts_opened': position_dates,
        'ts_closed': np.concatenate([position_dates[3:], [pd.NaT, pd.NaT, pd.NaT]]),  # Some still open
        'side': np.random.choice(['LONG', 'SHORT'], size=6),
        'quantity': np.random.uniform(50000, 200000, size=6),
        'avg_px_open': np.random.uniform(1.05, 1.25, size=6),
        'avg_px_close': np.concatenate([np.random.uniform(1.05, 1.25, 3), [np.nan, np.nan, np.nan]]),
        'realized_pnl': np.concatenate([np.random.normal(0, 500, 3), [np.nan, np.nan, np.nan]]),
        'unrealized_pnl': np.random.normal(0, 200, 6),
    })
    
    # Generate sample orders in Nautilus format  
    orders = pd.DataFrame({
        'client_order_id': [f'ORDER-{i:03d}' for i in range(10)],
        'venue_order_id': [f'VEN-{i:03d}' for i in range(10)],
        'strategy_id': ['MACDStrategy-000'] * 10,
        'instrument_id': ['EUR/USD.SIM'] * 10,
        'account_id': ['SIM-001'] * 10,
        'ts_init': trade_dates,
        'ts_accepted': trade_dates,
        'ts_triggered': trade_dates,
        'ts_filled': trade_dates,
        'order_side': trades['order_side'].values,
        'order_type': ['MARKET'] * 10,
        'quantity': trades['last_qty'].values,
        'price': trades['last_px'].values,
        'avg_px': trades['last_px'].values,
        'slippage': np.random.uniform(-0.0001, 0.0001, size=10),
        'status': ['FILLED'] * 10,
    })
    
    # Create balance and PnL data (required by BacktestResult)
    balance_history = pd.DataFrame({
        'timestamp': dates,
        'balance': equity_values * 0.95
    })
    
    pnl_realized = pd.DataFrame({
        'timestamp': position_dates[:3],  # Only closed positions
        'realized_pnl': positions['realized_pnl'].dropna().values
    })
    
    pnl_unrealized = pd.DataFrame({
        'timestamp': dates[::7],  # Weekly
        'unrealized_pnl': np.random.normal(0, 200, len(dates[::7]))
    })
    
    # Create BacktestResult
    result = BacktestResult(
        strategy_name="Demo Strategy",
        start_time=start_time,
        end_time=end_time,
        instruments=["DEMO_SYMBOL"],
        equity_curve=equity_curve,
        balance_history=balance_history,
        pnl_realized=pnl_realized,
        pnl_unrealized=pnl_unrealized,
        trades=trades,
        positions=positions,
        orders=orders,
        total_return=0.15,
        sharpe_ratio=1.2,
        max_drawdown=-0.08,
        win_rate=0.6,
        profit_factor=1.8,
        nautilus_result=None
    )
    
    return result

if __name__ == "__main__":
    print("Starting demo Flask server for React frontend...")
    print("This will serve backtest data on http://127.0.0.1:5001")
    print("The React frontend should be running on http://localhost:3000")
    print("\nPress Ctrl+C to stop the server")
    
    # Create demo data
    result = create_demo_data()
    
    # Start the visualizer server
    visualizer = LightweightChartsVisualizer(port=5001, auto_open=False)
    print("Starting Flask server with demo data...")
    visualizer.show(result)
    
    # Keep the server running
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")
        visualizer.stop()
