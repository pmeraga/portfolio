# etl_to_catalog.py
# Convert one or more Databento DBN artifacts under raw/ into a Nautilus Parquet Data Catalog.
# Usage (paths):
#   python -m data.etl_to_catalog \
#       --instrument-id ES.n.0.GLBX \
#       --paths raw/GLBX.MDP3__ES.n.0__continuous__trades__2023-12-06.dbn.zst \
#       --catalog-path catalog --overwrite
#
# Usage (manifest keys):
#   python -m data.etl_to_catalog \
#       --instrument-id ES.n.0.GLBX \
#       --artifacts key1 key2 \
#       --catalog-path catalog --overwrite
#
# Optional custom futures spec (single JSON string):
#   --instrument-spec-json '{"raw_symbol":"CL.n.0","venue_name":"NYMEX","price_increment":"0.01","price_precision":2,"multiplier":1000,"lot_size":1,"underlying":"WTI","asset_class":"COMMODITY","currency":"USD","expiry_date":"2099-12-31"}'

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from rich import print as rprint

# NautilusTrader imports
from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader
from nautilus_trader.model.currencies import USD  # extend mapping if needed
from nautilus_trader.model.enums import AssetClass
from nautilus_trader.model.identifiers import InstrumentId, Symbol
from nautilus_trader.model.instruments import FuturesContract
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# Data classes (only for counts/typing and optional filtering/inspection)
try:
    from nautilus_trader.model.data import Bar, QuoteTick, TradeTick, OrderBookDepth10  # noqa: F401
except Exception as e:
    raise RuntimeError(
        "Unable to import NautilusTrader data classes. Check your nautilus-trader install."
    ) from e


# ---------- Constants ----------
RAW_MANIFEST = Path("raw/manifest.json")


# ---------- Helpers ----------
def _iso_to_ns(s: str) -> int:
    """
    Convert an ISO 8601 string (e.g. '2023-12-31' or '2023-12-31T23:59:59Z') to Unix ns.
    Assumes UTC if no timezone provided.
    """
    if not s:
        raise ValueError("Empty ISO date for expiry.")
    s = s.strip()
    if "T" not in s:
        # Bare date → set to end of day UTC
        s = s + "T23:59:59Z"
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1_000_000_000)


def load_raw_manifest(manifest_path: Optional[Path] = None) -> Dict[str, Any]:
    path = manifest_path if manifest_path else RAW_MANIFEST
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"artifacts": {}}


def resolve_artifact_keys_or_paths(artifacts: List[str], paths: List[str], manifest_path: Optional[Path] = None) -> List[Path]:
    """
    If `paths` are provided, they are validated and returned.
    Otherwise interpret `artifacts` as keys in raw/manifest.json and return their file paths.
    """
    out: List[Path] = []

    if paths:
        for p in paths:
            pp = Path(p)
            if not pp.exists():
                raise FileNotFoundError(f"Path not found: {pp}")
            out.append(pp)
        return out

    if not artifacts:
        raise ValueError("Provide either --artifacts (manifest keys) or --paths (dbn files).")

    manifest = load_raw_manifest(manifest_path=manifest_path).get("artifacts", {})
    for k in artifacts:
        if k not in manifest:
            raise KeyError(f"Key not in manifest: {k}")
        out.append(Path(manifest[k]["path"]))
    return out


def to_ns(ts: Any) -> Optional[int]:
    """
    Best-effort convert known Nautilus timestamp-like attributes to int ns.
    """
    if ts is None:
        return None
    # Common patterns: object with .ns or .value or callable
    for attr in ("ns", "value", "timestamp", "ts_event", "to_nanoseconds"):
        try:
            v = getattr(ts, attr)
            return int(v() if callable(v) else v)
        except Exception:
            continue
    # Sometimes ts may already be int-ish
    try:
        return int(ts)
    except Exception:
        return None


def summarize_objects(objs: Iterable[object]) -> Tuple[Dict[str, int], Dict[str, Dict[str, int]]]:
    """
    Produce a class count and rough time bounds (min/max ns) per class for manifest.
    """
    counts: Dict[str, int] = defaultdict(int)
    ts_bounds: Dict[str, Dict[str, int]] = {}

    for o in objs:
        cls = type(o).__name__
        counts[cls] += 1
        # try to read an event timestamp-like attribute
        tse = None
        for attr in ("ts_event", "ts_event_ns", "open_time", "close_time", "ts_init", "ts"):
            tse = getattr(o, attr, None)
            if tse is not None:
                break
        ns = to_ns(tse)
        if ns is not None:
            b = ts_bounds.setdefault(cls, {"min": ns, "max": ns})
            b["min"] = min(b["min"], ns)
            b["max"] = max(b["max"], ns)
    return counts, ts_bounds


def create_generic_futures(
    instrument_id_str: str,
    instrument_spec_json: Optional[str] = None,
    default_expiry_iso: str = "2099-12-31T23:59:59Z",
) -> FuturesContract:
    """
    Build a FuturesContract for ANY instrument, optionally customized from a single JSON string.

    `instrument_spec_json` may include:
      - "raw_symbol": "ES.n.0" (or "CL.n.0", etc.)
      - "venue_name": "GLBX" (or "NYMEX", "COMEX", etc.)
      - "price_increment": "0.25"
      - "price_precision": 2
      - "multiplier": 50
      - "lot_size": 1
      - "underlying": "SPX"
      - "asset_class": "INDEX" | "COMMODITY" | ...
      - "currency": "USD"
      - "expiry_date": "2099-12-31" (ISO date/time)

    If omitted, ES-like safe defaults are applied and the venue/symbol fall back to `instrument_id_str`.
    """
    # Parse target id to derive defaults
    parsed_id = InstrumentId.from_str(instrument_id_str)
    default_venue = str(getattr(parsed_id, "venue", "GLBX"))
    default_symbol = str(getattr(parsed_id, "symbol", instrument_id_str))  # e.g., "ES.n.0"

    # Safe defaults (match a working ES config)
    spec: Dict[str, Any] = {
        "raw_symbol": default_symbol,
        "venue_name": default_venue,
        "asset_class": AssetClass.INDEX,
        "currency": USD,
        "price_increment": Decimal("0.25"),
        "price_precision": 2,
        "multiplier": 50,
        "lot_size": 1,
        "underlying": "SPX",
        "expiry_date": default_expiry_iso,
    }

    # Apply JSON overrides if provided
    if instrument_spec_json:
        overrides = json.loads(instrument_spec_json)

        # String fields
        for key in ("raw_symbol", "venue_name", "underlying", "expiry_date"):
            if key in overrides and overrides[key] is not None:
                spec[key] = str(overrides[key])

        # AssetClass enum mapping (upper-cased string)
        ac = overrides.get("asset_class")
        if ac is not None:
            ac_str = str(ac).upper()
            spec["asset_class"] = getattr(AssetClass, ac_str, spec["asset_class"])

        # Currency mapping (extend mapping as needed)
        cur = overrides.get("currency")
        if cur is not None and str(cur).upper() == "USD":
            spec["currency"] = USD

        # Numeric/decimal fields (accept numbers or strings)
        if "price_increment" in overrides and overrides["price_increment"] is not None:
            spec["price_increment"] = Decimal(str(overrides["price_increment"]))
        if "price_precision" in overrides and overrides["price_precision"] is not None:
            spec["price_precision"] = int(overrides["price_precision"])
        if "multiplier" in overrides and overrides["multiplier"] is not None:
            spec["multiplier"] = int(overrides["multiplier"])
        if "lot_size" in overrides and overrides["lot_size"] is not None:
            spec["lot_size"] = int(overrides["lot_size"])

    # Rebuild final InstrumentId using (possibly) overridden symbol/venue
    final_instr_id = InstrumentId.from_str(f"{spec['raw_symbol']}.{spec['venue_name']}")
    expiration_ns = _iso_to_ns(spec["expiry_date"])

    return FuturesContract(
        instrument_id=final_instr_id,
        raw_symbol=Symbol(spec["raw_symbol"]),
        asset_class=spec["asset_class"],
        currency=spec["currency"],
        price_precision=int(spec["price_precision"]),
        price_increment=Price.from_str(str(spec["price_increment"])),
        multiplier=Quantity.from_int(int(spec["multiplier"])),
        lot_size=Quantity.from_int(int(spec["lot_size"])),
        underlying=str(spec["underlying"]),
        activation_ns=0,
        expiration_ns=expiration_ns,  # far-future by default → avoids "reached expiration"
        ts_event=0,
        ts_init=0,
    )


def _filter_objects_for_instrument(objs: Iterable[object], instrument_id: InstrumentId) -> Iterable[object]:
    """
    Defensive filter: keep only objects that appear to belong to `instrument_id`.
    This is forgiving and only applied if objects expose recognizable attributes.
    """
    out = []
    target_str = str(instrument_id)
    target_raw = str(getattr(instrument_id, "symbol", ""))  # e.g., "ES.n.0"

    for o in objs:
        keep = True
        # Common attributes to check
        for attr in ("instrument_id", "id", "symbol", "raw_symbol"):
            if hasattr(o, attr):
                val = getattr(o, attr)
                sval = str(val)
                # If any attribute is present and mismatches clearly, drop it
                if target_str not in sval and target_raw and target_raw not in sval:
                    keep = False
                    break
        if keep:
            out.append(o)
    return out


# ---------- Main ETL ----------
def run_etl(
    instrument_id: str,
    artifacts: Optional[List[str]] = None,
    paths: Optional[List[str]] = None,
    catalog_path: str = "catalog",
    overwrite: bool = False,
    as_legacy_cython: bool = False,
    instrument_spec_json: Optional[str] = None,  # NEW: single-string custom spec
    raw_manifest_path: Optional[str] = None,  # NEW: configurable manifest path
) -> Dict[str, Any]:
    """
    Convert DBN artifacts to a Parquet Data Catalog. Returns a small manifest dict.
    - Writes the instrument FIRST (with a safe non-expiring default unless overridden)
    - Loads each .dbn.zst via DatabentoDataLoader and writes records to the catalog
    - Produces a manifest.json (class counts & rough time bounds) for quick inspection
    """
    artifacts = artifacts or []
    paths = paths or []

    # Use provided manifest path or fall back to default
    manifest_path = Path(raw_manifest_path) if raw_manifest_path else RAW_MANIFEST

    # Resolve artifacts/paths
    artifact_paths = resolve_artifact_keys_or_paths(artifacts, paths, manifest_path=manifest_path)

    # Prepare catalog directory
    catalog_dir = Path(catalog_path)
    if overwrite and catalog_dir.exists():
        import shutil
        shutil.rmtree(catalog_dir)
    catalog_dir.mkdir(parents=True, exist_ok=True)

    loader = DatabentoDataLoader()
    catalog = ParquetDataCatalog(catalog_dir)

    global_counts: Dict[str, int] = defaultdict(int)
    global_bounds: Dict[str, Dict[str, int]] = {}

    # Build a generic (possibly customized) futures instrument
    instrument = create_generic_futures(
        instrument_id_str=instrument_id,
        instrument_spec_json=instrument_spec_json,
        default_expiry_iso="2099-12-31T23:59:59Z",
    )

    # Write instrument to catalog FIRST (ensures id is present for subsequent writes)
    catalog.write_data([instrument])
    rprint(f"[green]Wrote instrument[/green]: {instrument.id}")

    # Load & write each artifact
    parsed_instr_id = InstrumentId.from_str(str(instrument.id))
    # Write to catalog safely
    for p in artifact_paths:
        rprint(f"[cyan]Loading[/cyan] {Path(p).name}")
        objs = loader.from_dbn_file(
            path=Path(p),
            instrument_id=parsed_instr_id,
            as_legacy_cython=as_legacy_cython,
        )

        counts, bounds = summarize_objects(objs)
        for k, v in counts.items():
            global_counts[k] += v
        for k, b in bounds.items():
            gb = global_bounds.setdefault(k, {"min": b["min"], "max": b["max"]})
            gb["min"] = min(gb["min"], b["min"])
            gb["max"] = max(gb["max"], b["max"])

        if not objs:
            continue

        try:
            catalog.write_data(objs)
        except AssertionError as e:
            if "Intervals are not disjoint" in str(e):
                rprint(f"[yellow]⚠ Overlapping intervals detected in {p.name}; retrying without disjoint check...[/yellow]")
                catalog.write_data(objs, skip_disjoint_check=True)
            else:
                raise


    # Emit a small manifest for quick QA (classes & time bounds)
    manifest = {
        "instrument_id": str(instrument.id),
        "classes": dict(global_counts),
        "time_bounds_ns": global_bounds,
        "catalog_path": str(catalog_dir),
    }
    (catalog_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    rprint(f"[green]Catalog ready[/green] at {catalog_dir}")
    rprint(manifest)
    return manifest


# ---------- CLI ----------
def main() -> None:
    ap = argparse.ArgumentParser(description="DBN → Nautilus Parquet Data Catalog")
    ap.add_argument("--instrument-id", required=True, help="e.g. ES.n.0.GLBX (venue optional; JSON can override)")
    ap.add_argument("--catalog-path", default="catalog", help="Output Parquet catalog directory")
    ap.add_argument("--artifacts", nargs="*", default=[], help="Manifest keys referencing raw DBN files")
    ap.add_argument("--paths", nargs="*", default=[], help="Direct .dbn.zst file paths")
    ap.add_argument("--overwrite", action="store_true", help="Delete catalog path before writing")
    ap.add_argument("--as-legacy-cython", action="store_true", help="Pass-through flag to DatabentoDataLoader")
    ap.add_argument(
        "--instrument-spec-json",
        default=None,
        help="Single JSON string to override instrument fields (tick size, multiplier, underlying, venue, expiry, etc.)",
    )
    args = ap.parse_args()

    run_etl(
        instrument_id=args.instrument_id,
        artifacts=args.artifacts,
        paths=args.paths,
        catalog_path=args.catalog_path,
        overwrite=args.overwrite,
        as_legacy_cython=args.as_legacy_cython,
        instrument_spec_json=args.instrument_spec_json,
    )


if __name__ == "__main__":
    main()
