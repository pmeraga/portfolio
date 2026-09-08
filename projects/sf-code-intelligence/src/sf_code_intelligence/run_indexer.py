"""
run_indexer.py – Walk a fixtures directory and index all Apex and Object files.

Usage: python -m sf_code_intelligence.run_indexer ./fixtures
"""

import sys
from pathlib import Path

from sf_code_intelligence.db import get_connection, init_db
from sf_code_intelligence.indexer import (
    build_dependency_edges,
    index_apex_class,
    index_object,
)


def run(fixtures_path: str):
    init_db()
    conn = get_connection()

    root = Path(fixtures_path)

    for cls_file in root.glob("classes/*.cls"):
        if "Test" not in cls_file.name:
            print(f"Indexing class: {cls_file.name}")
            index_apex_class(str(cls_file), conn)

    for obj_file in root.glob("objects/**/*.object-meta.xml"):
        print(f"Indexing object: {obj_file.name}")
        index_object(str(obj_file), conn)

    print("Building dependency edges...")
    build_dependency_edges(conn)

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "./fixtures")
