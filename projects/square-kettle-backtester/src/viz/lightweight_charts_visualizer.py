"""
LightweightCharts Visualizer for BacktestResult

This module provides a web-based visualization server that displays backtest results
using TradingView's lightweight-charts library. It converts BacktestResult data
into interactive charts showing equity curves, price action with trade markers,
and performance metrics.
"""

import json
import threading
import webbrowser
from datetime import datetime
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
import time
import signal
import subprocess

from data.schemas import BacktestResult


class LightweightChartsVisualizer:
    """
    Web-based visualizer for BacktestResult using lightweight-charts.
    
    Features:
    - Interactive equity curve chart
    - Price chart with trade markers
    - Performance metrics dashboard
    - Multiple timeframe support
    - Auto-opens browser on startup
    """
    
    def __init__(self, port: int = 5001, host: str = "127.0.0.1", auto_open: bool = True):
        """
        Initialize the visualizer.
        
        Args:
            port: Port number for the web server
            host: Host address for the web server  
            auto_open: Whether to automatically open browser
        """
        self.port = port
        self.host = host
        self.auto_open = auto_open
        # Locate built frontend files. Check common locations in order of preference:
        #  - src/viz/static/dist
        #  - src/viz/frontend/static/dist
        #  - src/viz/frontend/dist
        candidates = [
            Path(__file__).parent / "static" / "dist",
            Path(__file__).parent / "frontend" / "static" / "dist",
            Path(__file__).parent / "frontend" / "dist",
        ]
        frontend_dist: Optional[Path] = None
        for p in candidates:
            if p.exists():
                frontend_dist = p
                break

        static_folder_arg = str(frontend_dist) if frontend_dist is not None else None

        # Use Flask static_folder so the installed package can serve the built frontend
        self.app = Flask(__name__, static_folder=static_folder_arg, static_url_path='')
        
        # Configure CORS explicitly to allow frontend origin
        CORS(self.app, origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",  # React dev server alternate port
            "http://127.0.0.1:3001",
            "http://localhost:5173",  # Vite dev server default
            "http://127.0.0.1:5173"
        ])
        self.backtest_result: Optional[BacktestResult] = None
        self.backtest_results: Optional[Dict[str, BacktestResult]] = None  # For multiple strategies
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # Setup Flask routes
        self._setup_routes()
    
    
    def _setup_routes(self):
        """Setup Flask application routes."""
        
        @self.app.route('/')
        def index():
            """Main dashboard page - serve the built React frontend index.html if present.

            If no built frontend is available, fall back to a simple HTML message that
            instructs the user how to start the dev frontend.
            """
            # If frontend not built or no index.html, fallback message
            index_path = Path(self.app.static_folder) / 'index.html' if self.app.static_folder else None
            if index_path and index_path.exists():
                return self.app.send_static_file('index.html')

            if self.backtest_result is None:
                return "<h1>No backtest results loaded</h1><p>Call visualizer.show(backtest_result) first</p>"
            return "<h1>Flask API Server Running</h1><p>React frontend should be running on <a href='http://localhost:3000'>http://localhost:3000</a></p>"
        
        @self.app.route('/api/equity-curve')
        def equity_curve_data():
            """API endpoint for equity curve data."""
            if self.backtest_result is None:
                return jsonify({'error': 'No data loaded'})
            return jsonify(self._format_equity_curve())
        
        @self.app.route('/api/trade-markers')
        def trades_data():
            """API endpoint for trades data."""
            if self.backtest_result is None:
                return jsonify({'error': 'No data loaded'})
            return jsonify(self._format_trade_markers())
        
        @self.app.route('/api/price-data')
        def price_data():
            """API endpoint for price data (if available)."""
            if self.backtest_result is None:
                return jsonify({'error': 'No data loaded'})
            # For now, we'll construct price data from trades
            # In a full implementation, you'd load actual price data
            return jsonify(self._format_tooltip_price_actions())
        
        @self.app.route('/api/positions')
        def positions_data():
            """API endpoint for position data."""
            if self.backtest_result is None:
                return jsonify({'error': 'No data loaded'})
            return jsonify(self._format_positions())
        
        @self.app.route('/api/metrics')
        def metrics_data():
            """API endpoint for performance metrics."""
            if self.backtest_result is None:
                return jsonify({'error': 'No data loaded'})
            return jsonify(self._get_performance_metrics())
        
        @self.app.route('/api/custom-indicators')
        def custom_indicators_data():
            """API endpoint for custom indicators data."""
            if self.backtest_result is None:
                return jsonify({'error': 'No data loaded'})
            return jsonify(self._format_custom_indicators())
        
        @self.app.route('/api/trades-by-time-slot')
        def trades_by_time_slot():
            """API endpoint for trades data optimized for tooltip lookup."""
            if self.backtest_result is None:
                return jsonify({'error': 'No data loaded'})
            return jsonify(self._format_tooltip_trades())
        
        @self.app.route('/api/multiple-strategies')
        def multiple_strategies():
            """API endpoint for multiple strategies data."""
            if self.backtest_results is None:
                return jsonify({'error': 'No multiple strategies data loaded', 'has_multiple': False})
            return jsonify(self._format_multiple_strategies())
    
    def _format_tooltip_trades(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Format trades data for tooltip lookup.
        
        Returns:
            Dict where:
            - Keys are chart bar times (matching price data granularity)
            - Values are lists of individual trades with their precise timestamps
        """
        if self.backtest_result.trades.empty:
            return {}
        
        trades_df = self.backtest_result.trades.copy()
        
        # Nautilus fills report standard fields
        required_columns = ['ts_event', 'order_side', 'last_px', 'last_qty']
        missing_columns = [col for col in required_columns if col not in trades_df.columns]
        if missing_columns:
            raise ValueError(f"Missing required Nautilus fills columns: {missing_columns}")
        
        # Add normalized timestamp column
        trades_df['timestamp'] = pd.to_datetime(trades_df['ts_event'])
        trades_df = trades_df.sort_values('timestamp')
        
        # Determine time granularity (same as price data for alignment)
        temp_df = trades_df.rename(columns={'timestamp': 'norm_timestamp'})
        time_config = self._determine_time_granularity(temp_df)
        
        print(f"Trades lookup using {time_config['description']} granularity")
        
        # Group trades by chart bar time
        trades_df = trades_df.set_index('timestamp')
        trades_by_bar = {}
        
        for time_group, group in trades_df.groupby(pd.Grouper(freq=time_config['grouper'])):
            if group.empty:
                continue
            
            # Chart bar time (key for lookup)
            bar_time = time_group.strftime(time_config['format'])
            
            # List of individual trades with precise timestamps (millisecond precision)
            trades_list = []
            for _, trade in group.iterrows():
                # Get precise timestamp with milliseconds
                precise_time = trade.name
                
                # Format with milliseconds if available
                try:
                    precise_time_str = precise_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                except:
                    # Fallback to seconds if no microseconds
                    precise_time_str = precise_time.strftime('%Y-%m-%d %H:%M:%S')
                
                trades_list.append({
                    'ts_event': precise_time_str,  # Precise trade timestamp
                    'order_side': str(trade['order_side']),
                    'last_qty': float(trade['last_qty']),
                    'last_px': float(trade['last_px'])
                })
            
            trades_by_bar[bar_time] = trades_list
        
        print(f"Generated trades lookup with {len(trades_by_bar)} time bars containing {sum(len(v) for v in trades_by_bar.values())} total trades")
        
        return trades_by_bar

    def _format_equity_curve(self) -> List[Dict[str, Any]]:
        """Convert equity curve to lightweight-charts format with adaptive time granularity."""
        if self.backtest_result.equity_curve.empty:
            return []
        
        df = self.backtest_result.equity_curve.copy()
        
        # Convert timestamp to datetime if needed
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
        
        # Determine time granularity based on trades data if available
        time_config = {'format': '%Y-%m-%d', 'grouper': 'D', 'description': 'daily'}  # Default
        
        if not self.backtest_result.trades.empty:
            # Use same granularity as trades for alignment
            trades_df = self.backtest_result.trades.copy()
            timestamp_col = 'ts_event' if 'ts_event' in trades_df.columns else 'timestamp'
            trades_df['norm_timestamp'] = pd.to_datetime(trades_df[timestamp_col])
            time_config = self._determine_time_granularity(trades_df)
        
        print(f"Equity curve using {time_config['description']} granularity to match trades")
        
        # Set timestamp as index for grouping
        df = df.set_index('timestamp')
        
        # Group equity data by the same granularity as trades
        data = []
        seen_times = set()
        
        for time_group, group in df.groupby(pd.Grouper(freq=time_config['grouper'])):
            if group.empty:
                continue
            
            # Use the last equity value in each time bucket
            equity_value = float(group['equity_value'].iloc[-1])
            
            # Format time according to granularity
            time_str = time_group.strftime(time_config['format'])
            
            # Skip duplicate timestamps
            if time_str in seen_times:
                continue
            
            seen_times.add(time_str)
            data.append({
                'time': time_str,
                'value': equity_value
            })
        
        # If no grouped data, fall back to original logic
        if not data:
            # Sample data to max 10,000 points for performance
            max_points = 10000
            if len(df) > max_points:
                sample_indices = np.linspace(0, len(df) - 1, max_points).astype(int)
                df = df.iloc[sample_indices]
            
            for _, row in df.iterrows():
                time_value = row.name.strftime('%Y-%m-%d')
                if time_value not in seen_times:
                    seen_times.add(time_value)
                    data.append({
                        'time': time_value,
                        'value': float(row['equity_value'])
                    })
        
        # Sort by time to ensure ascending order
        return sorted(data, key=lambda x: x['time'])
    
    def _get_time_granularities(self) -> Dict[str, Dict[str, Any]]:
        """
        Get available time granularities with their formatting configurations.
        
        Returns:
            dict: Time granularities mapping
        """
        return {
            '1S': {'format': '%Y-%m-%d %H:%M:%S', 'bucket_size': '1sec', 'grouper': '1S', 'description': 'second'},
            '1T': {'format': '%Y-%m-%d %H:%M', 'bucket_size': '1min', 'grouper': '1T', 'description': 'minute'},
            '5T': {'format': '%Y-%m-%d %H:%M', 'bucket_size': '5min', 'grouper': '5T', 'description': '5-minute'},
            '15T': {'format': '%Y-%m-%d %H:%M', 'bucket_size': '15min', 'grouper': '15T', 'description': '15-minute'},
            '1H': {'format': '%Y-%m-%d %H:%M', 'bucket_size': '1hour', 'grouper': '1H', 'description': 'hourly'},
            '2H': {'format': '%Y-%m-%d %H:%M', 'bucket_size': '2hour', 'grouper': '2H', 'description': '2-hourly'},
            'D': {'format': '%Y-%m-%d', 'bucket_size': 'D', 'grouper': 'D', 'description': 'daily'},
            'W': {'format': '%Y-%m-%d', 'bucket_size': '1week', 'grouper': 'W', 'description': 'weekly'}
        }
    
    def _determine_time_granularity(self, trades_df: pd.DataFrame, overwrite: str | None = None) -> Dict[str, Any]:
        """
        Determine appropriate time granularity based on data characteristics.
        
        Returns:
            dict: Contains 'format', 'bucket_size', 'grouper', and 'description'
        """
        time_granularities = self._get_time_granularities()

        if overwrite and overwrite in time_granularities.keys():
            return time_granularities[overwrite]

        if trades_df.empty:
            return time_granularities['D']
        
        # Calculate time span of the backtest
        time_span = trades_df['norm_timestamp'].max() - trades_df['norm_timestamp'].min()
        total_seconds = time_span.total_seconds()
        num_trades = len(trades_df)
        
        # Calculate average trades per day to understand data density
        trades_per_day = num_trades / max(1, total_seconds / 86400)
        
        # Choose granularity based on time span and trade density
        if total_seconds <= 3600:  # 1 hour or less
            # High frequency - use seconds or minutes
            if trades_per_day > 100:  # High frequency
                return time_granularities['1T']
            else:
                return time_granularities['1S']
        elif total_seconds <= 86400:  # 1 day or less
            # Intraday - use minutes or hours
            if trades_per_day > 50:
                return time_granularities['5T']
            else:
                return time_granularities['15T']
        elif total_seconds <= 604800:  # 1 week or less
            # Short term - use hours
            return time_granularities['1H']
        elif total_seconds <= 2592000:  # 1 month or less
            # Medium term - use 2-hour or daily
            if trades_per_day > 10:
                return time_granularities['2H']
            else:
                return time_granularities['D']
        else:
            # Long term - use daily or weekly
            if trades_per_day > 2:
                return time_granularities['D']
            else:
                return time_granularities['W']
    
    def _format_trade_markers(self) -> List[Dict[str, Any]]:
        """Convert trades to markers format with adaptive time granularity to avoid grid effect."""
        if self.backtest_result.trades.empty:
            return []
        
        # The trades DataFrame uses Nautilus fills report field names (the standard)
        trades_df = self.backtest_result.trades.copy()
        
        # Nautilus fills report standard fields
        required_columns = ['ts_event', 'order_side', 'last_px', 'last_qty']
        missing_columns = [col for col in required_columns if col not in trades_df.columns]
        if missing_columns:
            raise ValueError(f"Missing required Nautilus fills columns: {missing_columns}. Available columns: {list(trades_df.columns)}")
        
        # Normalize data types using Nautilus field names
        trades_df['timestamp'] = pd.to_datetime(trades_df['ts_event'])
        trades_df['quantity'] = pd.to_numeric(trades_df['last_qty'], errors='coerce')
        trades_df['price'] = pd.to_numeric(trades_df['last_px'], errors='coerce')
        trades_df['side'] = trades_df['order_side'].astype(str).str.upper()
        
        # Filter out invalid data
        trades_df = trades_df.dropna(subset=['timestamp', 'quantity', 'price'])
        trades_df = trades_df[trades_df['quantity'] > 0]
        trades_df = trades_df[trades_df['price'] > 0]
        trades_df = trades_df.sort_values('timestamp')
        
        if trades_df.empty:
            return []
        
        # Create buy/sell flags
        trades_df['is_buy'] = trades_df['side'].isin(['BUY', 'LONG'])
        
        # Determine appropriate time granularity based on the timestamp column
        time_config = self._determine_time_granularity(trades_df.rename(columns={'timestamp': 'norm_timestamp'}))
        
        # Set timestamp as index for grouping
        trades_df = trades_df.set_index('timestamp')
        
        # Group trades by the determined time granularity to avoid overlapping markers
        grouped_trades = []
        
        for time_group, group in trades_df.groupby(pd.Grouper(freq=time_config['grouper'])):
            if group.empty:
                continue
            
            # Calculate aggregated trade info for this time bucket
            buy_trades = group[group['is_buy']]
            sell_trades = group[~group['is_buy']]
            
            total_buy_qty = buy_trades['quantity'].sum()
            total_sell_qty = sell_trades['quantity'].sum()
            
            # Use volume-weighted average price
            total_volume = group['quantity'].sum()
            if total_volume > 0:
                avg_price = (group['quantity'] * group['price']).sum() / total_volume
            else:
                avg_price = group['price'].mean()
            
            total_trades = len(group)
            
            # Format time according to granularity
            time_str = time_group.strftime(time_config['format'])
            
            # Determine net direction and create simplified marker
            if total_buy_qty > total_sell_qty:
                # Net buying
                net_qty = total_buy_qty - total_sell_qty
                is_net_buy = True
                marker_text = f"BUY {net_qty:.0f} @ ${avg_price:.2f}"
                if total_trades > 1:
                    marker_text += f" ({total_trades} trades)"
            elif total_sell_qty > total_buy_qty:
                # Net selling
                net_qty = total_sell_qty - total_buy_qty
                is_net_buy = False
                marker_text = f"SELL {net_qty:.0f} @ ${avg_price:.2f}"
                if total_trades > 1:
                    marker_text += f" ({total_trades} trades)"
            else:
                # Equal buying and selling - default to buy
                net_qty = total_buy_qty
                is_net_buy = True
                marker_text = f"BUY {net_qty:.0f} @ ${avg_price:.2f}"
                if total_trades > 1:
                    marker_text += f" ({total_trades} trades)"
            
            grouped_trades.append({
                'time': time_str,
                'is_buy': is_net_buy,
                'quantity': net_qty,
                'price': avg_price,
                'text': marker_text,
                'trade_count': total_trades,
            })
        
        # Calculate quantity range for proportional sizing
        quantities = [trade['quantity'] for trade in grouped_trades]
        min_qty, max_qty = (min(quantities), max(quantities)) if quantities else (1, 1)
        qty_range = max_qty - min_qty or 1
        
        # Convert to lightweight-charts markers
        markers = []
        for trade in grouped_trades:
            # create the text
            short_text = f"{trade['quantity']:.0f}"
            if trade['trade_count'] > 1:
                short_text += f" ({trade['trade_count']}x)"
            
            # Proportional size: 0.3-2.5 range based on quantity
            size = 0.3 + ((trade['quantity'] - min_qty) / qty_range) * 0.7
            
            marker = {
                'time': trade['time'],
                'position': 'aboveBar' if trade['is_buy'] else 'belowBar',
                'color': "#85BDEB" if trade['is_buy'] else "#F6DC8C",  # Blue for buy, yellow for sell
                'shape': 'arrowUp' if trade['is_buy'] else 'arrowDown',
                'size': max(0.1, min(3.0, size)),  # Clamp to valid range
                'text': short_text  # Shortened text for better display
            }
            markers.append(marker)
        
        # Log the chosen granularity for debugging
        print(f"Using {time_config['description']} granularity for {len(markers)} trade markers (from {len(trades_df)} trades)")
        
        return sorted(markers, key=lambda x: x['time'])
    
    def _format_tooltip_price_actions(self) -> List[Dict[str, Any]]:
        """Create comprehensive price data with granularity that matches trade aggregation."""
        if self.backtest_result.trades.empty:
            return []
        
        # Get trade data sorted by time - use Nautilus format
        trades_df = self.backtest_result.trades.copy()
        timestamp_col = 'ts_event' if 'ts_event' in trades_df.columns else 'timestamp'
        price_col = 'last_px' if 'last_px' in trades_df.columns else 'price'
        
        trades_df['timestamp_normalized'] = pd.to_datetime(trades_df[timestamp_col])
        trades_df = trades_df.sort_values('timestamp_normalized')
        
        # Determine the same time granularity as trades to ensure alignment
        temp_df = trades_df.rename(columns={'timestamp_normalized': 'norm_timestamp'})
        time_config = self._determine_time_granularity(temp_df)
        
        print(f"Price data using {time_config['description']} granularity to match trades")
        
        # Set timestamp as index for grouping
        trades_df = trades_df.set_index('timestamp_normalized')
        
        # Group trades by the same granularity used for trade markers
        price_data = []
        
        for time_group, group in trades_df.groupby(pd.Grouper(freq=time_config['grouper'])):
            if group.empty:
                continue
            
            # Get trades for this time bucket
            prices = group[price_col].astype(float)
            
            if not prices.empty:
                # Use actual trade prices for this time bucket
                open_price = float(prices.iloc[0])
                close_price = float(prices.iloc[-1])
                high_price = float(prices.max())
                low_price = float(prices.min())
                
                # Add small spread around trade prices for realism
                spread_pct = 0.0005  # 0.05% spread
                high_price = max(high_price, high_price * (1 + spread_pct))
                low_price = min(low_price, low_price * (1 - spread_pct))
                
                # Format time according to granularity (same as trades)
                time_str = time_group.strftime(time_config['format'])
                
                price_data.append({
                    'time': time_str,
                    'open': float(open_price),
                    'high': float(high_price),
                    'low': float(low_price),
                    'close': float(close_price)
                })
        
        return price_data
    
    def _format_positions(self) -> List[Dict[str, Any]]:
        """Convert positions to lightweight-charts format with adaptive time granularity."""
        # Always use synthetic position calculation from trades for running position visualization
        # Nautilus positions are closed position records, not running position states
        if not self.backtest_result.trades.empty:
            if not self.backtest_result.positions.empty:
                print(f"Found {len(self.backtest_result.positions)} position records, but using synthetic calculation from trades for running position visualization")
            else:
                print("No position data found - generating synthetic position data from trades")
            
            # Get trades data with proper field name detection
            trades_df = self.backtest_result.trades.copy()
            timestamp_col = 'ts_event' if 'ts_event' in trades_df.columns else 'timestamp'
            side_col = 'order_side' if 'order_side' in trades_df.columns else 'side'
            qty_col = 'last_qty' if 'last_qty' in trades_df.columns else 'quantity'
            
            print(f"Using fields: timestamp={timestamp_col}, side={side_col}, quantity={qty_col}")
            
            trades_df['timestamp_normalized'] = pd.to_datetime(trades_df[timestamp_col])
            trades_df = trades_df.sort_values('timestamp_normalized')
            
            # Calculate running position size from trades FIRST, then aggregate by time
            position_data = []
            running_position = 0.0
            
            # Add initial zero position before any trades
            start_time = trades_df['timestamp_normalized'].iloc[0] - pd.Timedelta(seconds=1)
            position_data.append({
                'timestamp': start_time,
                'position_size': 0.0
            })
            
            # Process each trade chronologically to build running position
            print(f"Processing {len(trades_df)} trades chronologically:")
            for i, (_, trade) in enumerate(trades_df.iterrows()):
                side = str(trade[side_col]).upper()
                quantity = float(trade[qty_col])
                
                # Update running position based on trade side
                if side in ['BUY', 'LONG']:
                    running_position += quantity
                    direction = '+'
                elif side in ['SELL', 'SHORT']:
                    running_position -= quantity
                    direction = '-'
                else:
                    direction = '?'
                
                # Debug first few trades
                if i < 5:
                    print(f"  Trade {i+1}: {side} {quantity} → {direction}{quantity} = {running_position}")
                
                position_data.append({
                    'timestamp': trade['timestamp_normalized'], 
                    'position_size': running_position
                })
            
            print(f"Final running position: {running_position}")
            
            # Now convert to DataFrame and group by time (AFTER calculating running positions)
            synthetic_positions = pd.DataFrame(position_data)
            
            # Determine time granularity to match trades
            temp_df = trades_df.rename(columns={'timestamp_normalized': 'norm_timestamp'})
            time_config = self._determine_time_granularity(temp_df)
            
            print(f"Aggregating positions using {time_config['description']} granularity")
            
            # Group by time granularity - take LAST position in each time bucket
            synthetic_positions = synthetic_positions.set_index('timestamp')
            data = []
            seen_times = set()
            
            for time_group, group in synthetic_positions.groupby(pd.Grouper(freq=time_config['grouper'])):
                if group.empty:
                    continue
                
                # Use the LAST (most recent) position in each time bucket
                final_position = float(group['position_size'].iloc[-1])
                time_str = time_group.strftime(time_config['format'])
                
                if time_str not in seen_times:
                    seen_times.add(time_str)
                    data.append({
                        'time': time_str,
                        'value': final_position
                    })
            
            print(f"Generated {len(data)} aggregated position points")
            if data:
                print(f"Position range: {data[0]['value']} → {data[-1]['value']}")
            
            return sorted(data, key=lambda x: x['time'])
        
        # No position data and no trades
        return []
    
    def _format_custom_indicators(self) -> Dict[str, List[Dict[str, Any]]]:
        """Convert custom indicators to lightweight-charts format."""
        if not self.backtest_result.custom_indicators:
            return {}
        
        result = {}
        
        # Determine time granularity based on trades for consistency
        time_config = {'format': '%Y-%m-%d', 'grouper': 'D', 'description': 'daily'}  # Default
        
        if not self.backtest_result.trades.empty:
            trades_df = self.backtest_result.trades.copy()
            timestamp_col = 'ts_event' if 'ts_event' in trades_df.columns else 'timestamp'
            trades_df['norm_timestamp'] = pd.to_datetime(trades_df[timestamp_col])
            time_config = self._determine_time_granularity(trades_df)
        
        print(f"Custom indicators using {time_config['description']} granularity to match trades")
        
        for indicator_name, indicator_df in self.backtest_result.custom_indicators.items():
            if indicator_df is None or indicator_df.empty:
                result[indicator_name] = []
                continue
            
            df = indicator_df.copy()
            
            # Handle different column names for timestamp
            timestamp_col = None
            for col in ['timestamp', 'time', 'ts', 'date']:
                if col in df.columns:
                    timestamp_col = col
                    break
            
            if timestamp_col is None:
                print(f"Warning: No timestamp column found in custom indicator '{indicator_name}'. Expected columns: {list(df.columns)}")
                result[indicator_name] = []
                continue
            
            # Handle different column names for values
            value_col = None
            for col in ['value', 'equity_value', 'price', 'close', 'val']:
                if col in df.columns:
                    value_col = col
                    break
            
            if value_col is None:
                print(f"Warning: No value column found in custom indicator '{indicator_name}'. Expected columns: {list(df.columns)}")
                result[indicator_name] = []
                continue
            
            # Convert timestamp to datetime
            df[timestamp_col] = pd.to_datetime(df[timestamp_col])
            df = df.sort_values(timestamp_col)
            
            # Set timestamp as index for grouping
            df = df.set_index(timestamp_col)
            
            # Group data by the same granularity as other charts
            data = []
            seen_times = set()
            
            for time_group, group in df.groupby(pd.Grouper(freq=time_config['grouper'])):
                if group.empty:
                    continue
                
                # Use the last value in each time bucket
                value = float(group[value_col].iloc[-1])
                
                # Format time according to granularity
                time_str = time_group.strftime(time_config['format'])
                
                # Skip duplicate timestamps
                if time_str in seen_times:
                    continue
                
                seen_times.add(time_str)
                data.append({
                    'time': time_str,
                    'value': value
                })
            
            # If no grouped data, fall back to original logic
            if not data:
                # Sample data to max 10,000 points for performance
                max_points = 10000
                if len(df) > max_points:
                    sample_indices = np.linspace(0, len(df) - 1, max_points).astype(int)
                    df = df.iloc[sample_indices]
                
                for _, row in df.iterrows():
                    time_value = row.name.strftime('%Y-%m-%d')
                    if time_value not in seen_times:
                        seen_times.add(time_value)
                        data.append({
                            'time': time_value,
                            'value': float(row[value_col])
                        })
            
            # Sort by time to ensure ascending order
            result[indicator_name] = sorted(data, key=lambda x: x['time'])
            print(f"Formatted custom indicator '{indicator_name}' with {len(result[indicator_name])} data points")
        
        return result
    
    def _format_multiple_strategies(self) -> Dict[str, Any]:
        """Format data for multiple strategies comparison."""
        if self.backtest_results is None:
            return {'has_multiple': False}
        
        strategies_data = {}
        for strategy_name, result in self.backtest_results.items():
            # Format equity curve for each strategy
            equity_data = []
            if not result.equity_curve.empty:
                df = result.equity_curve.copy()
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp')
                
                # Use same time granularity as single strategy
                time_config = {'format': '%Y-%m-%d', 'grouper': 'D', 'description': 'daily'}
                if not result.trades.empty:
                    trades_df = result.trades.copy()
                    timestamp_col = 'ts_event' if 'ts_event' in trades_df.columns else 'timestamp'
                    trades_df['norm_timestamp'] = pd.to_datetime(trades_df[timestamp_col])
                    time_config = self._determine_time_granularity(trades_df)
                
                df = df.set_index('timestamp')
                for time_group, group in df.groupby(pd.Grouper(freq=time_config['grouper'])):
                    if not group.empty:
                        equity_data.append({
                            'time': time_group.strftime(time_config['format']),
                            'value': float(group['equity_value'].iloc[-1])
                        })
            
            strategies_data[strategy_name] = {
                'equity_curve': sorted(equity_data, key=lambda x: x['time']),
                'metrics': {
                    'total_return': result.total_return,
                    'sharpe_ratio': result.sharpe_ratio,
                    'max_drawdown': result.max_drawdown,
                    'win_rate': result.win_rate,
                    'profit_factor': result.profit_factor,
                    'total_trades': len(result.trades),
                },
                'strategy_name': result.strategy_name,
            }
        
        return {
            'has_multiple': True,
            'strategies': strategies_data,
            'strategy_names': list(strategies_data.keys())
        }
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get formatted performance metrics."""
        if self.backtest_result is None:
            return {}
        
        return {
            'total_return': f"{self.backtest_result.total_return:.2%}",
            'sharpe_ratio': f"{self.backtest_result.sharpe_ratio:.2f}" if self.backtest_result.sharpe_ratio else "N/A",
            'max_drawdown': f"{self.backtest_result.max_drawdown:.2%}",
            'win_rate': f"{self.backtest_result.win_rate:.2%}",
            'profit_factor': f"{self.backtest_result.profit_factor:.2f}" if self.backtest_result.profit_factor else "N/A",
            'total_trades': len(self.backtest_result.trades),
            'start_time': self.backtest_result.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': self.backtest_result.end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'strategy_name': self.backtest_result.strategy_name,
            'instruments': ', '.join(self.backtest_result.instruments)
        }
    
    def show(self, backtest_result: BacktestResult | Dict[str, BacktestResult]) -> str:
        """
        Start the Flask API server for the React frontend.
        
        Args:
            backtest_result: BacktestResult object or dict of strategy_name -> BacktestResult
                           to visualize. If dict, multiple strategies will be shown.
            
        Returns:
            str: URL where the API server is running
        """
        # Handle both single result and multiple results
        if isinstance(backtest_result, dict):
            self.backtest_results = backtest_result
            # Use first result as primary for backward compatibility
            self.backtest_result = next(iter(backtest_result.values()))
        else:
            self.backtest_result = backtest_result
            self.backtest_results = None
        
        # Start the server
        self._start_server()
        
        url = f"http://{self.host}:{self.port}"
        
        if self.auto_open:
            # Give the server a moment to start
            time.sleep(1)
            # Don't open the API server URL since we want users to use React frontend
            print(f"Flask API server running at: {url}")
            print(f"React frontend should be running at: http://localhost:3000")
        else:
            print(f"Flask API server running at: {url}")
        
        return url
    
    def _start_server(self):
        """Start the Flask server in a separate thread."""
        if self.is_running:
            print(f"Server already running on {self.host}:{self.port}")
            return
        
        def run_server():
            # Disable Flask's startup messages
            import logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.WARNING)
            
            self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True
    
    def stop(self):
        """Stop the visualization server."""
        if self.server_thread and self.is_running:
            print("Stopping visualization server...")
            self.is_running = False
            stop_flask_servers(self.port)


def stop_flask_servers(port):
    """Safely stop Flask servers running on the specified port."""
    try:
        # Try to find processes using the port
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = [pid.strip() for pid in result.stdout.strip().split('\n') if pid.strip()]
            
            if pids:
                print(f"Found {len(pids)} process(es) using port {port}")
                
                # Try graceful termination first (SIGTERM)
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except (OSError, ValueError):
                        pass  # Process might already be gone
                
                # Wait a moment for graceful shutdown
                time.sleep(1)
                
                # Check if any processes are still running and force kill if needed
                for pid in pids:
                    try:
                        os.kill(int(pid), 0)  # Check if process exists
                        os.kill(int(pid), signal.SIGKILL)
                    except (OSError, ValueError):
                        pass  # Process is already gone
                
                print("Stopped existing Flask server(s)")
            else:
                print(f"No processes found using port {port}")
        else:
            print(f"No processes found using port {port}")
            
    except FileNotFoundError:
        print("lsof command not available, skipping port cleanup")
    except subprocess.TimeoutExpired:
        print("Timeout while checking for processes, skipping cleanup")
    except Exception as e:
        print(f"Error during port cleanup: {e}")


if __name__ == "__main__":
    print("LightweightCharts Visualizer")
    print("Use: visualizer = LightweightChartsVisualizer()")
    print("     url = visualizer.show(backtest_result)")
    print("Or:  url = visualize_backtest(backtest_result)")
