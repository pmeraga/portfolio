"""Tiny live smoke test: verify TPUF SDK signatures + Voyage embedding + connectivity.

Run: .venv/bin/python scripts/smoke_tpuf.py
This does ONLY read-only queries with small top_k. It does NOT fetch namespace metadata.
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import turbopuffer
import voyageai

TPUF_KEY = os.environ["TURBOPUFFER_API_KEY"]
VOYAGE_KEY = os.environ["VOYAGE_API_KEY"]
REGION = os.environ.get("TPUF_REGION", "aws-us-west-2")
NAMESPACE = os.environ.get("TPUF_NAMESPACE", "search-test-v4")


def main() -> None:
    tpuf = turbopuffer.Turbopuffer(api_key=TPUF_KEY, region=REGION)
    ns = tpuf.namespace(NAMESPACE)
    vo = voyageai.Client(api_key=VOYAGE_KEY)

    print("== Embedding query with voyage-3 ==")
    emb = vo.embed("software engineers", model="voyage-3").embeddings[0]
    print(f"embedding dim = {len(emb)}")

    print("\n== Stage 1a: dense ANN query (top_k=3) ==")
    res = ns.query(rank_by=("vector", "ANN", emb), top_k=3, include_attributes=True)
    print(f"num rows = {len(res.rows)}")
    r0 = res.rows[0]
    # Show the attribute keys to confirm schema
    keys = sorted(k for k in r0.__dict__.keys()) if hasattr(r0, "__dict__") else []
    try:
        model_keys = sorted(list(r0.model_dump().keys()))
    except Exception:
        model_keys = []
    print("row attribute keys (model_dump):", model_keys[:60])
    print("id:", r0.id, "| name:", getattr(r0, "name", None), "| country:", getattr(r0, "country", None))
    print("has rerankSummary:", "rerankSummary" in r0)
    rs = getattr(r0, "rerankSummary", None)
    print("rerankSummary[:160]:", (rs[:160] if isinstance(rs, str) else rs))
    print("deg_degrees:", getattr(r0, "deg_degrees", None))
    print("$dist present:", "$dist" in r0, "->", getattr(r0, "$dist", None) if "$dist" in r0 else "n/a")

    print("\n== Stage 1b: BM25 full-text query on rerankSummary (top_k=3) ==")
    res2 = ns.query(rank_by=("rerankSummary", "BM25", "tax lawyer IRS audit"), top_k=3, include_attributes=True)
    print(f"num rows = {len(res2.rows)}")
    for r in res2.rows:
        print("  ", r.id, "|", getattr(r, "name", None), "| $dist:", getattr(r, "$dist", None) if "$dist" in r else None)

    print("\n== Stage 1c: filter test (ContainsAny on deg_degrees) ==")
    try:
        res3 = ns.query(
            rank_by=("vector", "ANN", emb),
            top_k=3,
            include_attributes=True,
            filters=("deg_degrees", "ContainsAny", ["Doctorate", "Master's"]),
        )
        print(f"filtered num rows = {len(res3.rows)}; first degs:", getattr(res3.rows[0], "deg_degrees", None))
    except Exception as e:
        print("ContainsAny filter error:", type(e).__name__, str(e)[:200])

    print("\n== Stage 1d: BM25 with Contains filter (And) ==")
    try:
        res4 = ns.query(
            rank_by=("rerankSummary", "BM25", "radiologist MRI CT"),
            top_k=3,
            include_attributes=True,
            filters=("And", [("country", "Eq", "United States")]),
        )
        print(f"And/Eq filtered num rows = {len(res4.rows)}; first country:", getattr(res4.rows[0], "country", None))
    except Exception as e:
        print("And/Eq filter error:", type(e).__name__, str(e)[:200])

    print("\nSMOKE OK")


if __name__ == "__main__":
    sys.exit(main())
