# src/data/fetch_databento.py
from __future__ import annotations
"""
Idempotent Databento downloader with content-addressed caching.

Usage:
  python -m data.fetch_databento \
    --dataset GLBX.MDP3 \
    --symbols ES.n.0 \
    --stype-in continuous \
    --schema tbbo \
    --start 2023-12-06T14:30:00Z \
    --end   2023-12-06T20:30:00Z
"""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional  # <-- import Optional here

from rich import print as rprint
import databento as db  # pip install databento

RAW_DIR = Path("raw")
MANIFEST_PATH = RAW_DIR / "manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(manifest_path: Optional[Path] = None) -> Dict[str, Any]:
    path = manifest_path if manifest_path else MANIFEST_PATH
    if path.exists():
        return json.loads(path.read_text())
    return {"artifacts": {}}


def save_manifest(m: Dict[str, Any], manifest_path: Optional[Path] = None) -> None:
    path = manifest_path if manifest_path else MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(m, indent=2))


def build_key(dataset: str, symbols: List[str], stype_in: str, schema: str, start: str, end: str) -> str:
    payload = "|".join([
        dataset.strip(),
        ",".join(sorted([s.strip() for s in symbols])),
        stype_in.strip(),
        schema.strip(),
        start.strip(),
        end.strip(),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def safe_symkey(symbols: List[str]) -> str:
    return "+".join(s.replace("/", "_").replace(":", "_") for s in symbols)


def iso_to_stamp(s: str) -> str:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%Y%m%dT%H%M%SZ")
    except Exception:
        return s


def get_api_key(cli_key: Optional[str]) -> str:
    if cli_key:
        return cli_key
    # try .env if available, otherwise env
    try:
        from dotenv import load_dotenv  # optional
        load_dotenv()
    except Exception:
        pass
    env_key = os.getenv("DATABENTO_API_KEY")
    if not env_key:
        raise RuntimeError("DATABENTO_API_KEY not provided (CLI, .env, or environment).")
    return env_key


def artifact_path(dataset: str, symbols: List[str], stype_in: str, schema: str, start: str, end: str, key: str, raw_dir: Optional[Path] = None) -> Path:
    base_dir = raw_dir if raw_dir else RAW_DIR
    return base_dir / f"{dataset}__{safe_symkey(symbols)}__{stype_in}__{schema}__{iso_to_stamp(start)}__{iso_to_stamp(end)}__{key}.dbn.zst"


def run_fetch(
    dataset: str,
    symbols: List[str],
    stype_in: str,
    schema: str,
    start: str,
    end: str,
    api_key: Optional[str] = None,
    force: bool = False,
    notes: str = "",
    raw_dir: Optional[str] = None,
) -> Dict[str, Any]:
    # Use provided raw_dir or fall back to default
    target_raw_dir = Path(raw_dir) if raw_dir else RAW_DIR
    target_manifest = target_raw_dir / "manifest.json"

    # Ensure directory exists
    target_raw_dir.mkdir(exist_ok=True, parents=True)

    key = build_key(dataset, symbols, stype_in, schema, start, end)
    path = artifact_path(dataset, symbols, stype_in, schema, start, end, key, raw_dir=target_raw_dir)

    manifest = load_manifest(manifest_path=target_manifest)
    entry = manifest["artifacts"].get(key)

    if entry and Path(entry["path"]).exists() and not force:
        rprint(f"[green]Cache hit[/green]: {entry['path']}")
        return entry

    # Resolve API key and create client
    api_key = get_api_key(api_key)
    try:
        client = db.Historical(api_key=api_key)  # newer SDKs
    except TypeError:
        os.environ["DATABENTO_API_KEY"] = api_key  # older SDKs read from env
        client = db.Historical()

    rprint(f"[cyan]Fetching[/cyan] {dataset} {symbols} {schema} {start}→{end}")
    path.parent.mkdir(parents=True, exist_ok=True)

    client.timeseries.get_range(
        dataset=dataset,
        symbols=symbols,
        stype_in=stype_in,
        schema=schema,
        start=start,
        end=end,
        path=str(path),
    )

    sha = sha256_file(path)
    size = path.stat().st_size
    created_at = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    entry = {
        "key": key,
        "dataset": dataset,
        "symbols": symbols,
        "stype_in": stype_in,
        "schema": schema,
        "start": start,
        "end": end,
        "path": str(path),
        "sha256": sha,
        "bytes": size,
        "created_at_utc": created_at,
        "record_count": None,
        "notes": notes,
    }
    manifest["artifacts"][key] = entry
    save_manifest(manifest, manifest_path=target_manifest)
    rprint(f"[green]Saved[/green] {path} ({size:,} bytes)")
    rprint(f"[dim]Manifest updated at {target_manifest}[/dim]")
    return entry


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch Databento DBN with caching.")
    p.add_argument("--dataset", required=True, help="e.g. GLBX.MDP3")
    p.add_argument("--symbols", required=True, nargs="+", help="e.g. ES.n.0 or GC.n.0 GC.n.1")
    p.add_argument("--stype-in", required=True, help="e.g. continuous or native")
    p.add_argument(
        "--schema",
        required=True,
        choices=[
            # tick-by-tick
            "tbbo", "tcbbo", "trades",
            # order book
            "mbo", "mbp-1", "mbp-10", "cmbp-1",
            # OHLCV bars
            "ohlcv-1s", "ohlcv-1m", "ohlcv-1h", "ohlcv-1d",
            # BBO bars (aggregated)
            "bbo-1s", "bbo-1m", "cbbo-1s", "cbbo-1m",
            # misc/reference
            "definition", "statistics", "status", "imbalance", "ohlcv-eod",
        ],
    )
    p.add_argument("--start", required=True, help="ISO8601 start (UTC)")
    p.add_argument("--end", required=True, help="ISO8601 end (UTC)")
    p.add_argument("--api-key", default=None, help="Overrides DATABENTO_API_KEY")
    p.add_argument("--force", action="store_true", help="Redownload even if cached")
    p.add_argument("--notes", default="", help="Free-text tag stored in manifest")
    args = p.parse_args()

    run_fetch(
        dataset=args.dataset,
        symbols=args.symbols,
        stype_in=args.stype_in,
        schema=args.schema,
        start=args.start,
        end=args.end,
        api_key=args.api_key,
        force=args.force,
        notes=args.notes,
    )


if __name__ == "__main__":
    main()
