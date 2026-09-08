# src/data/show_manifest_cli.py
from __future__ import annotations  # must be first

import argparse, json
from pathlib import Path
from typing import Dict, Any, List
from data.fetch_databento import build_key


def lookup_manifest_entries(raw_dir: str, dataset: str, symbols: List[str], stype_in: str, start: str, end: str, schemas: List[str]) -> Dict[str, Dict[str, Any]]:
    mpath = Path(raw_dir) / "manifest.json"
    out: Dict[str, Dict[str, Any]] = {}
    if not mpath.exists():
        return out
    m = json.loads(mpath.read_text())
    for schema in schemas:
        key = build_key(dataset, symbols, stype_in, schema, start, end)
        ent = m.get("artifacts", {}).get(key)
        if ent:
            out[schema] = ent
        else:
            out[schema] = {}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Show manifest entries for given request params.")
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--symbols", required=True, help="space-separated")
    ap.add_argument("--stype-in", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--schemas", required=True, help="space-separated")
    args = ap.parse_args()

    symbols = args.symbols.split()
    schemas = args.schemas.split()

    entries = lookup_manifest_entries(args.raw, args.dataset, symbols, args.stype_in, args.start, args.end, schemas)
    for schema in schemas:
        print(f"\nSchema: {schema}")
        ent = entries.get(schema) or {}
        if not ent:
            print("  (no entry)")
            continue
        for k in ("path","bytes","sha256","created_at_utc","dataset","symbols","stype_in","schema","start","end"):
            print(f"  {k}: {ent.get(k)}")


if __name__ == "__main__":
    main()
