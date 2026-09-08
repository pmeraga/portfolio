# src/data/csv_extract.py
"""
Extract normalized CSVs (trades, quotes, bars_for_viz) either from DBN files
(using DatabentoDataLoader) or from an existing Nautilus Parquet catalog.

Usage (from DBN):
  python -m data.csv_extract \
    --source dbn \
    --instrument-id ES.n.0 \
    --paths raw/....dbn.zst raw/....dbn.zst \
    --out-dir interim

Usage (from catalog):
  python -m data.csv_extract \
    --source catalog \
    --instrument-id ES.n.0 \
    --catalog-path catalog \
    --out-dir interim
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Dict, Optional

import pandas as pd
from rich import print as rprint

from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader

try:
    from nautilus_trader.model.identifiers import InstrumentId
except Exception:
    from nautilus_trader.model import InstrumentId  # type: ignore

try:
    from nautilus_trader.model.data import Bar, QuoteTick, TradeTick, OrderBookDepth10
except Exception as e:
    raise RuntimeError("Unable to import Nautilus data classes.") from e

from .schemas import (
    validate_trades_df,
    validate_quotes_df,
    validate_bars_df,
    enrich_quotes,
)


def to_ns(obj) -> int | None:
    for attr in ("ts_event_ns", "ts_event", "open_time", "ts_init", "ts"):
        v = getattr(obj, attr, None)
        if v is None:
            continue
        try:
            # v may be an object with .ns or int-like
            if hasattr(v, "ns"):
                return int(v.ns)
            return int(v)
        except Exception:
            continue
    return None


def rows_from_objects(objs: Iterable[object], instrument_id: str) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {"trades": [], "quotes": [], "bars": []}
    # We cannot know dataset/symbol from Nautilus objects reliably; keep placeholders if missing
    for o in objs:
        cls = type(o).__name__
        if cls == "TradeTick" or isinstance(o, TradeTick):
            out["trades"].append({
                "ts_event_ns": to_ns(o),
                "ts_recv_ns": getattr(getattr(o, "ts_recv", None), "ns", None)
                               or getattr(o, "ts_recv_ns", None) or to_ns(o),
                "instrument_id": instrument_id,
                "symbol": getattr(o, "symbol", None) or "",
                "price": float(getattr(o, "price",
                                       getattr(getattr(o, "price", None), "as_double", lambda: 0.0)())),
                "size": float(getattr(o, "size",
                                      getattr(getattr(o, "size", None), "as_double", lambda: 0.0)())),
                "dataset": "",
            })
        elif cls == "QuoteTick" or isinstance(o, QuoteTick):
            bid_px = float(getattr(o, "bid_price",
                                   getattr(getattr(o, "bid_price", None), "as_double", lambda: 0.0)()))
            ask_px = float(getattr(o, "ask_price",
                                   getattr(getattr(o, "ask_price", None), "as_double", lambda: 0.0)()))
            out["quotes"].append({
                "ts_event_ns": to_ns(o),
                "ts_recv_ns": getattr(getattr(o, "ts_recv", None), "ns", None)
                               or getattr(o, "ts_recv_ns", None) or to_ns(o),
                "instrument_id": instrument_id,
                "symbol": getattr(o, "symbol", None) or "",
                "bid_price": bid_px,
                "bid_size": float(getattr(o, "bid_size",
                                          getattr(getattr(o, "bid_size", None), "as_double", lambda: 0.0)())),
                "ask_price": ask_px,
                "ask_size": float(getattr(o, "ask_size",
                                          getattr(getattr(o, "ask_size", None), "as_double", lambda: 0.0)())),
                "source": "catalog_or_dbn",
            })
        elif cls == "Bar" or isinstance(o, Bar):
            # bar span best-effort: in seconds if available
            span_s = None
            if hasattr(o, "bar_span"):
                try:
                    span_s = int(getattr(o.bar_span, "seconds", None) or int(o.bar_span))
                except Exception:
                    span_s = None
            out["bars"].append({
                "ts_start_ns": getattr(getattr(o, "open_time", None), "ns", None) or to_ns(o),
                "ts_end_ns": getattr(getattr(o, "close_time", None), "ns", None) or to_ns(o),
                "instrument_id": instrument_id,
                "symbol": getattr(o, "symbol", None) or "",
                "open": float(getattr(o, "open",
                                      getattr(getattr(o, "open", None), "as_double", lambda: 0.0)())),
                "high": float(getattr(o, "high",
                                      getattr(getattr(o, "high", None), "as_double", lambda: 0.0)())),
                "low": float(getattr(o, "low",
                                     getattr(getattr(o, "low", None), "as_double", lambda: 0.0)())),
                "close": float(getattr(o, "close",
                                       getattr(getattr(o, "close", None), "as_double", lambda: 0.0)())),
                "volume": float(getattr(o, "volume",
                                        getattr(getattr(o, "volume", None), "as_double", lambda: 0.0)())),
                "bar_span_s": span_s or 0,
                "dataset": "",
            })
        else:
            # OrderBookDepth10 etc. currently not exported to CSV (would require TBBO aggregation)
            pass
    return out


def dataframes_from_rows(rows: Dict[str, List[dict]]) -> Dict[str, Optional[pd.DataFrame]]:
    """Transform accumulated rows into validated DataFrames (None if empty)."""
    out: Dict[str, Optional[pd.DataFrame]] = {"trades": None, "quotes": None, "bars": None}
    if rows["trades"]:
        df_t = pd.DataFrame(rows["trades"]).dropna(subset=["ts_event_ns"])
        df_t = validate_trades_df(df_t)
        out["trades"] = df_t
    if rows["quotes"]:
        df_q = pd.DataFrame(rows["quotes"]).dropna(subset=["ts_event_ns"])
        df_q = enrich_quotes(df_q)
        df_q = validate_quotes_df(df_q)
        out["quotes"] = df_q
    if rows["bars"]:
        df_b = pd.DataFrame(rows["bars"]).dropna(subset=["ts_start_ns", "ts_end_ns"])
        df_b = validate_bars_df(df_b)
        out["bars"] = df_b
    return out


def write_csvs(
    dfs: Dict[str, Optional[pd.DataFrame]],
    out_dir: Path,
    filename_prefix: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Optional[str]] = {"trades": None, "quotes": None, "bars": None}
    if dfs["trades"] is not None:
        p = out_dir / (f"{filename_prefix}_trades.csv" if filename_prefix else "trades.csv")
        dfs["trades"].to_csv(p, index=False)
        rprint(f"[green]Wrote[/green] {p} ({len(dfs['trades']):,} rows)")
        paths["trades"] = str(p)
    if dfs["quotes"] is not None:
        p = out_dir / (f"{filename_prefix}_quotes.csv" if filename_prefix else "quotes.csv")
        dfs["quotes"].to_csv(p, index=False)
        rprint(f"[green]Wrote[/green] {p} ({len(dfs['quotes']):,} rows)")
        paths["quotes"] = str(p)
    if dfs["bars"] is not None:
        p = out_dir / (f"{filename_prefix}_bars_for_viz.csv" if filename_prefix else "bars_for_viz.csv")
        dfs["bars"].to_csv(p, index=False)
        rprint(f"[green]Wrote[/green] {p} ({len(dfs['bars']):,} rows)")
        paths["bars"] = str(p)
    return paths


def _catalog_fetch_any(
    catalog: ParquetDataCatalog,
    cls,
    kind: str,
    instrument_id: str,
):
    """
    Try modern typed methods first (bars/quote_ticks/trade_ticks) then fall back to query().
    Returns an iterable (which we immediately list() at call site).
    """
    # Prefer typed convenience methods if present (support multiple API signatures)
    try:
        if kind == "bars" and hasattr(catalog, "bars"):
            try:
                return catalog.bars(instrument_id=instrument_id)
            except TypeError:
                return catalog.bars(instrument_ids=[instrument_id])
        if kind == "quotes" and hasattr(catalog, "quote_ticks"):
            try:
                return catalog.quote_ticks(instrument_id=instrument_id)
            except TypeError:
                return catalog.quote_ticks(instrument_ids=[instrument_id])
        if kind == "trades" and hasattr(catalog, "trade_ticks"):
            try:
                return catalog.trade_ticks(instrument_id=instrument_id)
            except TypeError:
                return catalog.trade_ticks(instrument_ids=[instrument_id])
    except Exception:
        pass
    # Fallback to generic query API if available
    try:
        if hasattr(catalog, "query"):
            return catalog.query(cls, identifiers=[instrument_id])
    except Exception:
        pass
    # Give up (older/different API)
    raise AttributeError("Catalog API does not expose a compatible reader for this data type.")


def run_csv_extract(
    source: str,
    instrument_id: str,
    paths: Optional[List[str]] = None,
    catalog_path: str = "catalog",
    out_dir: str = "interim",
    filename_prefix: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Orchestrates extraction to CSVs and returns dict of output file paths.
    """
    instr = InstrumentId.from_str(instrument_id)
    rows: Dict[str, List[dict]] = {"trades": [], "quotes": [], "bars": []}

    if source == "dbn":
        if not paths:
            raise ValueError("Provide --paths with DBN files for --source dbn")
        loader = DatabentoDataLoader()
        saw_any_depth = False
        for p in paths:
            objs = loader.from_dbn_file(path=Path(p), instrument_id=instr, as_legacy_cython=False)
            # Collect class names to warn if user only loaded depth
            cls_names = {type(o).__name__ for o in objs[:10]} if hasattr(objs, "__getitem__") else set()
            if "OrderBookDepth10" in cls_names:
                saw_any_depth = True
            chunk = rows_from_objects(objs, instrument_id=instrument_id)
            for k in rows:
                rows[k].extend(chunk[k])
        if saw_any_depth and not rows["quotes"]:
            rprint("[yellow]Note[/yellow]: you loaded depth (e.g., mbp-10). That does not produce QuoteTick CSVs "
                   "unless you also fetch a quote schema (tbbo/bbo) or synthesize TBBO from depth.")
    else:  # source == "catalog"
        catalog = ParquetDataCatalog(catalog_path)
        # Bars
        try:
            bars_iter = _catalog_fetch_any(catalog, Bar, "bars", instrument_id)
            rows["bars"].extend(rows_from_objects(list(bars_iter), instrument_id)["bars"])
        except Exception as e:
            rprint(f"[yellow]Skipping[/yellow] Bar: {e}")
        # Quotes
        try:
            quotes_iter = _catalog_fetch_any(catalog, QuoteTick, "quotes", instrument_id)
            rows["quotes"].extend(rows_from_objects(list(quotes_iter), instrument_id)["quotes"])
        except Exception as e:
            rprint(f"[yellow]Skipping[/yellow] QuoteTick: {e}")
        # Trades
        try:
            trades_iter = _catalog_fetch_any(catalog, TradeTick, "trades", instrument_id)
            rows["trades"].extend(rows_from_objects(list(trades_iter), instrument_id)["trades"])
        except Exception as e:
            rprint(f"[yellow]Skipping[/yellow] TradeTick: {e}")

        if not rows["quotes"]:
            rprint("[yellow]Note[/yellow]: Catalog contains no QuoteTick rows. If you only ETL'd depth (mbp-10), "
                   "add tbbo/bbo to your fetch+ETL to get quotes.")
        if not rows["trades"]:
            rprint("[yellow]Note[/yellow]: Catalog contains no TradeTick rows. Add 'trades' schema to fetch+ETL.")

    dfs = dataframes_from_rows(rows)
    return write_csvs(dfs, Path(out_dir), filename_prefix=filename_prefix)


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract normalized CSVs from DBN or Nautilus catalog.")
    ap.add_argument("--source", choices=["dbn", "catalog"], required=True)
    ap.add_argument("--instrument-id", required=True)
    ap.add_argument("--paths", nargs="*", default=[], help="DBN files when --source dbn")
    ap.add_argument("--catalog-path", default="catalog", help="Parquet Data Catalog when --source catalog")
    ap.add_argument("--out-dir", default="interim", help="Output directory for CSVs")
    args = ap.parse_args()

    run_csv_extract(
        source=args.source,
        instrument_id=args.instrument_id,
        paths=args.paths,
        catalog_path=args.catalog_path,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()