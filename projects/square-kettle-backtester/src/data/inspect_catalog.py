# src/data/inspect_catalog.py
"""
Quick sanity inspection of the Parquet Data Catalog.

CLI Usage:
  python -m data.inspect_catalog --catalog-path catalog

Programmatic Usage:
  from data.inspect_catalog import inspect_catalog_summary
  summary = inspect_catalog_summary("catalog", instrument_id="ES.n.0")
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Optional, Dict, Any

from rich.table import Table
from rich.console import Console

from nautilus_trader.persistence.catalog import ParquetDataCatalog

try:
    from nautilus_trader.model.identifiers import InstrumentId
except Exception:
    from nautilus_trader.model import InstrumentId  # type: ignore

try:
    from nautilus_trader.model.data import Bar, QuoteTick, TradeTick, OrderBookDepth10
except Exception as e:
    raise RuntimeError("Unable to import Nautilus data classes.") from e


def inspect_catalog_summary(catalog_path: str = "catalog", instrument_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Return a summary of the catalog contents as a dictionary.
    Uses manifest.json if available, otherwise probes the catalog directly.
    """
    cpath = Path(catalog_path)

    # Prefer manifest.json (written by ETL step)
    manifest = cpath / "manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text())
        return {
            "manifest_path": str(manifest),
            "classes": data.get("classes", {}),
            "time_bounds_ns": data.get("time_bounds_ns", {}),
        }

    # Fallback: probe catalog directly
    catalog = ParquetDataCatalog(cpath)
    classes = [TradeTick, QuoteTick, Bar, OrderBookDepth10]
    summary: Dict[str, Any] = {"classes": {}}
    for cls in classes:
        try:
            instr = InstrumentId.from_str(instrument_id) if instrument_id else None
            it = catalog.read_data(data_cls=cls, instrument_id=instr) if instr else catalog.read_data(data_cls=cls)
            count = 0
            for _ in it:
                count += 1
                if count >= 1000:  # stop early for performance
                    break
            summary["classes"][cls.__name__] = f"≥{count}"
        except Exception as e:
            summary["classes"][cls.__name__] = f"err: {e}"
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect Nautilus Parquet Data Catalog contents.")
    ap.add_argument("--catalog-path", default="catalog")
    ap.add_argument("--instrument-id", default=None, help="Optional: filter by a specific instrument")
    args = ap.parse_args()

    console = Console()
    summary = inspect_catalog_summary(args.catalog_path, args.instrument_id)

    if "manifest_path" in summary:
        console.print(f"[green]Catalog manifest[/green] {summary['manifest_path']}")
        tbl = Table("Class", "Count", "t_min (ns)", "t_max (ns)")
        classes = summary.get("classes", {})
        bounds = summary.get("time_bounds_ns", {})
        for cls, cnt in classes.items():
            b = bounds.get(cls, {})
            tbl.add_row(cls, f"{cnt:,}", str(b.get("min", "")), str(b.get("max", "")))
        console.print(tbl)
    else:
        console.print("[yellow]No manifest.json found, probed catalog directly.[/yellow]")
        tbl = Table("Class", "Rows (sample)")
        for cls, note in summary["classes"].items():
            tbl.add_row(cls, str(note))
        console.print(tbl)


if __name__ == "__main__":
    main()
