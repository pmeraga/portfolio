# src/data/paths_cli.py
from __future__ import annotations  # must be first

import argparse
from pathlib import Path
from data.fetch_databento import build_key, artifact_path


def compute_artifact_paths(dataset: str, symbols: list[str], stype_in: str, schemas: list[str], start: str, end: str) -> list[str]:
    out: list[str] = []
    for schema in schemas:
        key = build_key(dataset, symbols, stype_in, schema, start, end)
        p = artifact_path(dataset, symbols, stype_in, schema, start, end, key)
        out.append(Path(p).as_posix())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Print expected raw artifact path(s).")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--symbols", required=True, help="space-separated, e.g. 'ES.n.0'")
    ap.add_argument("--stype-in", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--schema", help="single schema, e.g. 'mbp-10'")
    ap.add_argument("--schemas", help="space-separated schemas, e.g. 'ohlcv-1m mbp-10'")
    args = ap.parse_args()

    symbols = args.symbols.split()
    schemas = [args.schema] if args.schema else (args.schemas.split() if args.schemas else None)
    if not schemas:
        raise SystemExit("Provide --schema or --schemas")

    for p in compute_artifact_paths(args.dataset, symbols, args.stype_in, schemas, args.start, args.end):
        print(p)


if __name__ == "__main__":
    main()
