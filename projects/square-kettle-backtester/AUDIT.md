# Codebase Audit Report

This audit identifies critical bugs, architectural issues, and improvement opportunities in the backtesting framework. Issues are prioritized based on their impact on system stability, correctness, user experience, and maintainability.

---

## Issue Prioritization Framework

Issues are prioritized using the following criteria:

1. **Critical (P0):** Bugs that cause incorrect results, crashes, or data corruption
2. **High (P1):** Missing core functionality, significant UX issues, or architectural flaws
3. **Medium (P2):** Code quality issues, missing tests, or minor UX improvements
4. **Low (P3):** Nice-to-have improvements, documentation gaps

---

## Critical Issues (P0)

### 1. Exception Handling Bug in `run_backtest.py` (Line 232)
**Location:** `src/backtest/run_backtest.py:227-232`  
**Severity:** Critical  
**Impact:** Silent failures, incorrect error reporting

**Issue:**
```python
try:
    pnl_unrealized = compute_unrealized_series_from_reports(equity_curve, positions_df)
except Exception:
    # Fallback to empty series if something unexpected happens during computation
    pnl_unrealized = pd.DataFrame(columns=["timestamp", "unrealized_pnl"])
    raise  # Bug: raises exception after creating fallback DataFrame
```

**Problem:** The code creates a fallback DataFrame but then immediately raises the exception, making the fallback useless. This masks the actual error and provides incorrect data.

**Fix:** Remove the `raise` statement or log the error before raising, or handle specific exceptions differently.

**Priority Justification:** Provides incorrect data while masking the real error. Users may not notice until later analysis, potentially leading to incorrect trading decisions.

---

### 2. Timestamp Conversion Warning: Nanoseconds Discarded
**Location:** `src/backtest/run_backtest.py:254`  
**Severity:** Critical  
**Impact:** Loss of precision, potential timing errors

**Issue:**
```python
start_time = pd.to_datetime(equity_curve["timestamp"].iloc[0], utc=True).to_pydatetime()
# Warning: Discarding nonzero nanoseconds in conversion
```

**Problem:** Converting pandas Timestamps with nanoseconds to Python datetime objects loses nanosecond precision. This can cause timing misalignments in high-frequency trading scenarios.

**Fix:** Use `pd.Timestamp` throughout or preserve nanoseconds using `pd.Timestamp.value` (nanoseconds since epoch).

**Priority Justification:** Loss of precision can affect backtest accuracy, especially for high-frequency strategies that rely on precise timestamps.

---

### 3. Data Quality Issue: Crossed Quotes Not Filtered
**Location:** `src/data/schemas.py:127-134`, `src/data/csv_extract.py:145`  
**Severity:** Critical  
**Impact:** Incorrect execution prices, unrealistic backtest results

**Issue:**
```python
if (df["bid_price"] > df["ask_price"]).any():
    bad_rows = (df["bid_price"] > df["ask_price"]).sum()
    warnings.warn(
        f"[quotes] Detected {bad_rows} crossed quotes (bid_price > ask_price). "
        f"These rows will be kept for traceability — consider filtering before analysis.",
        ...
    )
```

**Problem:** Crossed quotes (bid > ask) are kept in the data, which can lead to:
- Incorrect execution prices in backtests
- Unrealistic fill prices
- Invalid spread calculations

**Fix:** Filter crossed quotes before analysis, or use mid-price fallback when bid/ask are invalid.

**Priority Justification:** Directly affects backtest accuracy and can cause significant errors in execution simulation. Real market data should not have crossed quotes.

---

## High Priority Issues (P1)

### 4. Missing Multiple Strategies Support
**Location:** `examples/example-01-importing-data-and-using-the-backtester/quickstart.ipynb`  
**Severity:** High  
**Impact:** Cannot compare strategies side-by-side, limited analysis capability

**Issue:** The pipeline only supports running a single strategy at a time. There's no built-in way to:
- Run multiple strategies simultaneously
- Compare strategy performance side-by-side
- Visualize multiple strategies on the same chart

**Required Feature:** 
- Support multiple strategies in `BacktestEngineConfig`
- Aggregate results from multiple strategies
- Visualization option to show both strategies simultaneously

**Priority Justification:** Explicitly requested in assessment requirements. Essential for strategy comparison and optimization.

---

### 5. Custom Indicators Not Integrated at Strategy Level
**Location:** `examples/example-01-importing-data-and-using-the-backtester/quickstart.ipynb:Cell 17`  
**Severity:** High  
**Impact:** Indicators must be added post-backtest, not during strategy execution

**Issue:** Custom indicators are currently added to `BacktestResult` after the backtest completes:
```python
# Add the custom indicators to the backtest result
backtest_result.custom_indicators = custom_indicators
```

**Problem:** 
- Indicators should be calculated during strategy execution
- Strategy logic cannot access custom indicators for decision-making
- Indicators are disconnected from actual trading signals

**Required Feature:**
- Allow strategies to define and calculate custom indicators
- Store indicators alongside strategy execution
- Display indicators in dashboard automatically

**Priority Justification:** Explicitly requested in assessment requirements. Essential for strategy development and debugging.

---

### 6. No Dynamic Candlestick Sizing Based on Zoom
**Location:** `src/viz/frontend/src/components/PriceChart.jsx`  
**Severity:** High  
**Impact:** Poor UX when analyzing different timeframes

**Issue:** Charts use fixed time granularity (determined at data load time). Users cannot dynamically change candlestick duration (1m, 5m, 1h, 2h, 1d) based on zoom level.

**Required Feature:**
- Detect zoom level in lightweight-charts
- Dynamically aggregate price data to appropriate timeframe
- Support: 1m, 5m, 1h, 2h, 1d based on visible time range

**Priority Justification:** Explicitly requested in assessment requirements. Significantly improves user experience.

---

### 7. No Real-Time Streaming of Backtest Results
**Location:** `src/backtest/run_backtest.py`, `src/viz/lightweight_charts_visualizer.py`  
**Severity:** High  
**Impact:** Users must wait for entire backtest to complete before seeing results

**Issue:** Mentioned in README as an improvement area. Backtest results are only available after the entire backtest completes. For long-running backtests, this provides poor feedback.

**Required Feature:**
- Stream equity curve updates during backtest execution
- Update visualization in real-time as backtest progresses
- Provide progress indicators

**Priority Justification:** Explicitly mentioned in README as improvement area. Improves developer experience for long backtests.

---

## Medium Priority Issues (P2)

### 8. Minimal Test Coverage
**Location:** `unit_test/`  
**Severity:** Medium  
**Impact:** Risk of regressions, difficult to refactor safely

**Issue:** Only `test_run_backtest.py` exists with good coverage. Missing tests for:
- Data pipeline (`etl_to_catalog.py`, `fetch_databento.py`)
- Visualization components
- Strategy execution
- Edge cases in data validation

**Fix:** Add comprehensive unit tests for:
- Data validation functions
- Backtest result calculations
- Visualization data formatting
- Strategy execution logic

**Priority Justification:** Explicitly mentioned in README. Essential for maintainability and prevents regressions.

---

### 9. Incomplete Documentation and Docstrings
**Location:** Throughout codebase  
**Severity:** Medium  
**Impact:** Difficult for new developers to understand and extend

**Issue:** Many functions lack comprehensive docstrings. Examples folder could be expanded with more use cases.

**Fix:**
- Add detailed docstrings to all public functions
- Document function parameters, return values, exceptions
- Add more example notebooks demonstrating different scenarios
- Document architecture and design decisions

**Priority Justification:** Explicitly mentioned in README. Improves developer experience and onboarding.

---

### 10. Code Organization: Strategy Definition in Notebook
**Location:** `examples/example-01-importing-data-and-using-the-backtester/quickstart.ipynb:Cell 12`  
**Severity:** Medium  
**Impact:** Strategies cannot be easily reused or tested independently

**Issue:** Strategy classes are defined inline in the notebook, making them:
- Hard to reuse across different notebooks
- Difficult to unit test
- Not following separation of concerns

**Fix:** 
- Move strategies to `src/strategies/` module
- Create base strategy classes with common functionality
- Enable strategies to be imported and configured easily

**Priority Justification:** Improves code organization and makes strategies testable and reusable.

---

## Low Priority Issues (P3)

### 11. Port Cleanup Uses Platform-Specific Command
**Location:** `src/viz/lightweight_charts_visualizer.py:823-871`  
**Severity:** Low  
**Impact:** Port cleanup fails on Windows (lsof not available)

**Issue:** Uses `lsof` command which is Unix-only. Windows users see warning but functionality still works.

**Fix:** Use cross-platform solution (e.g., `psutil` library or socket-based port checking).

**Priority Justification:** Low impact. Affects developer experience on Windows.

---

### 12. Hardcoded Time Granularity Logic
**Location:** `src/viz/lightweight_charts_visualizer.py:315-365`  
**Severity:** Low  
**Impact:** Time granularity selection is complex and hard to configure

**Issue:** `_determine_time_granularity()` uses complex heuristics. Hard to override or customize for specific use cases.

**Fix:** 
- Make granularity configurable via API parameter
- Simplify logic or make it more explicit
- Allow user override

**Priority Justification:** Current implementation works but is complex. Would improve flexibility.

---


## Notes

Some issues are intentionally included in the codebase as part of the assessment. Focus should be on high-impact changes that demonstrate technical judgment.

