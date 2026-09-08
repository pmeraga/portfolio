"""
Test suite for DataBento + NautilusTrader integration.
Tests all components except the actual API call (which requires API key).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def test_core_imports():
    """Test that core packages (DataBento and NautilusTrader) can be imported."""
    import databento as db
    assert db.__version__ is not None
    
    import nautilus_trader as nt
    assert nt.__version__ is not None


def test_nautilus_components():
    """Test that key NautilusTrader components can be imported."""
    from nautilus_trader.persistence.catalog import ParquetDataCatalog
    from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.model.data import Bar, QuoteTick, TradeTick, OrderBookDepth10
    
    assert ParquetDataCatalog is not None
    assert DatabentoDataLoader is not None
    assert InstrumentId is not None


def test_custom_integration_modules():
    """Test that custom DataBento integration modules can be imported."""
    from data.fetch_databento import run_fetch, build_key, artifact_path
    from data.etl_to_catalog import run_etl, resolve_artifact_keys_or_paths
    
    assert run_fetch is not None
    assert build_key is not None
    assert artifact_path is not None


def test_key_generation_and_paths():
    """Test content-addressed key generation and artifact path construction."""
    from data.fetch_databento import build_key, artifact_path
    
    key = build_key(
        dataset="GLBX.MDP3",
        symbols=["ES.n.0"], 
        stype_in="continuous",
        schema="tbbo",
        start="2023-12-06T14:30:00Z",
        end="2023-12-06T15:00:00Z"
    )
    assert key is not None
    assert len(key) > 0
    
    path = artifact_path(
        dataset="GLBX.MDP3",
        symbols=["ES.n.0"],
        stype_in="continuous", 
        schema="tbbo",
        start="2023-12-06T14:30:00Z",
        end="2023-12-06T15:00:00Z",
        key=key
    )
    assert path is not None
    assert path.name is not None


def test_databento_loader():
    """Test DatabentoDataLoader initialization."""
    from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader
    from nautilus_trader.model.identifiers import InstrumentId
    
    loader = DatabentoDataLoader()
    assert loader is not None
    
    instrument = InstrumentId.from_str("ES.n.0")
    assert instrument is not None


def test_parquet_data_catalog():
    """Test ParquetDataCatalog creation and initialization."""
    from nautilus_trader.persistence.catalog import ParquetDataCatalog
    
    with tempfile.TemporaryDirectory() as tmpdir:
        catalog = ParquetDataCatalog(tmpdir)
        assert catalog is not None


def test_backtest_integration():
    """Test that backtest integration modules can be imported."""
    from backtest.run_backtest import run_backtest
    from data.schemas import BacktestResult
    
    assert run_backtest is not None
    assert BacktestResult is not None
