# Unit Tests

Testing conventions for this project.

## Running Tests

Run all tests with pytest:
```bash
pytest unit_test/
```

Run a specific test file:
```bash
pytest unit_test/test_run_backtest.py
pytest unit_test/test_databento_integration.py
```

## Test File Naming & Structure

### ✅ Standard Tests (`test_*.py`)

Use **pytest** format for production tests:

```python
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_something():
    """Each function starting with 'test_' is a test case."""
    assert some_value == expected_value
```

**Files:**
- `test_run_backtest.py` - Unit tests for backtest logic
- `test_databento_integration.py` - Integration tests for DataBento components

## Key Points

1. **All test files need sys.path setup** to import from `src/` modules
2. **Use pytest assertions** (`assert`) instead of unittest style
3. **Use descriptive function names** (`test_feature_name()`)
4. **Add docstrings** to test functions explaining what they test
