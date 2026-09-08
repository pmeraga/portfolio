# Sample Market Data

Pre-cached ES futures data for backtester assessment. No Databento API key required.

## Data Details
- **Instrument:** ES.n.0 (E-mini S&P 500 Futures)
- **Venue:** CME Globex (GLBX)
- **Period:** December 1-8, 2023
- **Schemas:**
  - trades: Actual trade executions
  - tbbo: Top-of-book quotes (bid/ask)
  - ohlcv-1m: 1-minute OHLCV bars

## Data Contents
- `raw/`: Original compressed DBN files from Databento
- `catalog/`: Processed Parquet catalog for Nautilus

## Usage
The quickstart notebook is pre-configured to use this data.
Simply run the notebook cells in order - no data fetching required.
