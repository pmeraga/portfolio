# Backtester Take-Home Assessment

**Portfolio context:** Square Kettle software engineering take-home work on a supplied backtesting framework. This snapshot includes fixes to PnL exception handling and quote validation, visualization improvements, and unit tests. The original assessment documentation follows.

Welcome! This repository contains a snapshot of an old version of our production backtesting system.

**Important:** Some parts have been intentionally modified to include flaws and issues for you to discover and address. This is not production-ready code - it's a realistic test environment.

## What This Is

A Python-based backtesting framework for trading strategies using real market data. It uses:
- **NautilusTrader** for backtesting engine https://nautilustrader.io/docs/
- **Databento** data format (pre-cached sample included)
- **Real ES futures data** from December 2023

## Quick Start (5 minutes)

### Requirements
- Python 3.11 or 3.12 only
- No API keys needed (sample data included)

### Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/Scripts/activate

# Install dependencies
pip install -e .

# Install Jupyter (for running the quickstart)
pip install jupyterlab
```

### Run the Quickstart

```bash
jupyter lab examples/example-01-importing-data-and-using-the-backtester/quickstart.ipynb
```

Run all cells sequentially. The notebook uses pre-cached data in `sample_data/` - no fetching required.

## Your Task

We want to see how you approach working with an unfamiliar codebase and handle ambiguous requirements - just like real work.

### Suggested Starting Points (Obvious Improvements)

These are explicitly suggested areas to explore:

1. **Testing:** Add unit tests (current coverage is minimal)
2. **Documentation**: Improve docstrings add more examples [here](examples/)
3. **Code Organization:** Refactor for better structure
4. **Visualization:** Doesn't stream backtest result as backtest is running

### Hidden Issues (Discovery Required)

Some things are intentionally broken or suboptimal, but not obviously so:
- Play with the backtester and observe its behavior
- Run backtests with different parameters
- Look at the output data and visualizations
- Some bugs may only appear in specific scenarios

**This is intentional** - part of the assessment is discovering issues on your own.

## Time Expectation

- **Recommended:** 2-4 hours
- **Focus:** Quality over quantity
- **Document:** Your thought process (commits, comments, notes)

## Evaluation Criteria

We're looking for:
1. **Code Quality:** Clean, readable, well-tested code
2. **Problem Solving:** How you identify and fix issues
3. **Handling Ambiguity:** Working without complete specifications
4. **Communication:** Clear commits, comments, documentation
5. **Judgment:** Prioritization and decision-making

## Troubleshooting

### "Python version not supported"
Use Python 3.11 or 3.12 only. Check with: `python --version`

### "No data found" or "Catalog empty"
The sample data should be in `sample_data/`. If missing, check that git cloned properly.

### "DATABENTO_API_KEY not found" error
This is expected because you the assessment doesn't require fetching new data.
If you run into this error, simply avoid using databento to fetch data by using the provided data in `sample_data/`.

If you're experimenting with data fetching:
- The assessment doesn't require fetching new data
- Set the environment variable if you have your own key:
  ```bash
  export DATABENTO_API_KEY="your-key"
  ```

### Jupyter not found
Install in your virtual environment: `pip install jupyterlab`

### Import errors
Make sure you:
1. Activated your virtual environment
2. Ran `pip install -r requirements.txt`
3. Ran `pip install -e .`

## Questions?

If you encounter issues with the assessment setup (not the intentional bugs!), reach out to your contact `andrew.yin@squarekettle.com`.

Good luck! 🚀
