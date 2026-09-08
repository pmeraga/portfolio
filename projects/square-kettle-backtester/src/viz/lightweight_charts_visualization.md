# LightweightCharts Visualization

This document describes the LightweightCharts visualization system for displaying backtest results in an interactive web interface.

## Overview

The `LightweightChartsVisualizer` class provides a web-based visualization server that displays `BacktestResult` data using TradingView's lightweight-charts library. It creates professional-quality financial charts with interactive features.

## Features

- **Interactive Equity Curve**: Line chart showing portfolio equity over time
- **Price Chart with Trade Markers**: Candlestick or line chart with buy/sell markers
- **Performance Metrics Dashboard**: Key performance indicators displayed as cards
- **Auto-Browser Opening**: Automatically opens the visualization in your default browser
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Updates**: Charts update dynamically as data changes

## Quick Start

### Basic Usage

```python
from viz.lightweight_charts_visualizer import visualize_backtest

# Assuming you have a BacktestResult object
url = visualize_backtest(backtest_result)
# Browser opens automatically to display the charts
```

### Advanced Usage

```python
from viz.lightweight_charts_visualizer import LightweightChartsVisualizer

# Create visualizer with custom settings
visualizer = LightweightChartsVisualizer(
    port=5001,           # Custom port
    host="127.0.0.1",    # Host address
    auto_open=False      # Don't auto-open browser
)

# Display the results
url = visualizer.show(backtest_result)
print(f"View charts at: {url}")

# Stop the server when done
visualizer.stop()
```

## Installation Requirements

The visualization system requires Flask for the web server:

```bash
pip install "flask>=3.0.0"
```

This dependency is included in the project's `requirements.txt`.

## API Reference

### LightweightChartsVisualizer

#### Constructor

```python
LightweightChartsVisualizer(port=5000, host="127.0.0.1", auto_open=True)
```

**Parameters:**
- `port` (int): Port number for the web server (default: 5000)
- `host` (str): Host address for the web server (default: "127.0.0.1")
- `auto_open` (bool): Whether to automatically open browser (default: True)

#### Methods

##### show(backtest_result)

Display backtest results in web browser.

**Parameters:**
- `backtest_result` (BacktestResult): The backtest results to visualize

**Returns:**
- `str`: URL where the visualization is served

##### stop()

Stop the visualization server.

### Convenience Function

#### visualize_backtest(backtest_result, port=5000, auto_open=True)

Quick function to visualize backtest results.

**Parameters:**
- `backtest_result` (BacktestResult): The backtest results to visualize
- `port` (int): Port number for the web server (default: 5000)
- `auto_open` (bool): Whether to automatically open browser (default: True)

**Returns:**
- `str`: URL where the visualization is served

## Charts and Visualizations

### Equity Curve Chart

- **Type**: Line chart
- **Data**: Portfolio equity value over time
- **Features**: 
  - Crosshair for precise value reading
  - Responsive resizing
  - Professional styling

### Price Chart with Trade Markers

- **Type**: Candlestick or line chart (auto-detected based on data)
- **Data**: Price data derived from trades
- **Features**:
  - Buy markers (blue arrows pointing up)
  - Sell markers (red arrows pointing down)
  - Hover tooltips showing trade details
  - Interactive crosshair

### Performance Metrics Dashboard

Key metrics displayed as cards:
- **Total Return**: Overall portfolio performance
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Ratio of gross profit to gross loss
- **Total Trades**: Number of executed trades

## Data Format Requirements

The visualizer expects a `BacktestResult` object with the following DataFrames:

### Required Data

- `equity_curve`: DataFrame with columns `['timestamp', 'equity_value']`
- `trades`: DataFrame with columns `['timestamp', 'instrument', 'side', 'price', 'quantity', 'pnl']`

### Optional Data

- `balance_history`: Account balance over time
- `pnl_realized`: Realized profit/loss events
- `pnl_unrealized`: Unrealized profit/loss over time
- `positions`: Position open/close events
- `orders`: Order execution details

## Customization

### Styling

The visualization uses a clean, professional design with:
- Light theme optimized for readability
- Responsive grid layout for metrics
- TradingView-style chart appearance
- Consistent color scheme (blue for buys, red for sells)

### Chart Configuration

Charts are configured with:
- Professional color scheme
- Interactive crosshairs
- Responsive sizing
- Grid lines for easy reading
- Appropriate time scaling

## Examples

### Demo Script

Run the included demo to see the visualizer in action:

```bash
python examples/lightweight_charts_demo.py
```

The demo provides three options:
1. **Basic usage**: Auto-opens browser with sample data
2. **Advanced usage**: Manual browser opening with custom configuration
3. **Sample data creation**: Generate and optionally save sample data

### Integration with Backtesting

```python
from backtest.run_backtest import run_backtest
from viz.lightweight_charts_visualizer import visualize_backtest

# Run your backtest
result = run_backtest(strategy_class, strategy_config)

# Visualize the results
visualize_backtest(result)
```

## Troubleshooting

### Common Issues

1. **Flask not installed**: Install with `pip install "flask>=3.0.0"`
2. **Port already in use**: Change the port number in the constructor
3. **Browser doesn't open**: Set `auto_open=False` and open the URL manually
4. **Empty charts**: Ensure your BacktestResult has data in the required format

### Error Handling

The visualizer includes comprehensive error handling:
- Empty data validation
- Missing column handling
- Network error recovery
- Graceful degradation for missing data

## Performance Considerations

- **Memory Usage**: Charts are rendered client-side, reducing server memory usage
- **Network Traffic**: Data is served via JSON API endpoints
- **Scalability**: Single-user visualization server (not intended for production deployment)
- **Browser Compatibility**: Uses modern JavaScript (requires recent browser)

## Technical Details

### Architecture

- **Backend**: Flask web server serving JSON API endpoints
- **Frontend**: HTML/CSS/JavaScript with lightweight-charts library
- **Data Flow**: BacktestResult → JSON API → Interactive Charts
- **Threading**: Server runs in background thread to avoid blocking

### Dependencies

- `flask>=3.0.0`: Web server framework
- `pandas`: Data manipulation (already required by project)
- `numpy`: Numerical operations (already required by project)

### Browser Requirements

- Modern browser with JavaScript support
- Support for ES6+ features (async/await, fetch API)
- HTML5 Canvas support (for chart rendering)

## Future Enhancements

Potential future improvements:
- Multiple strategy comparison
- Real-time data streaming
- Additional chart types (volume, indicators)
- Export functionality (PNG, PDF)
- Dark theme support
- Custom indicator overlays
