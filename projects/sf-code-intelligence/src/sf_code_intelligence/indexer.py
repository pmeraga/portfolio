"""
indexer.py – Index Salesforce metadata into SQLite.

Run via:  python -m sf_code_intelligence.run_indexer ./fixtures
"""

import json
import re
import sqlite3
from pathlib import Path

from lxml import etree

_CLASS_RE = re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)")
_SHARING_RE = re.compile(r"\b(with|without|inherited)\s+sharing\b", re.IGNORECASE)
_ANNOTATION_NAME_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")
_METHOD_RE = re.compile(
    r"(?P<ann>(?:^\s*@[^\n]*\n)*)"
    r"^\s*(?:(?:public|private|protected|global)\s+)?"
    r"(?P<mods>(?:(?:static|virtual|override|final|webservice|abstract)\s+)*)"
    r"(?P<rtype>[A-Za-z_][A-Za-z0-9_<>\[\],.?]*)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{",
    re.MULTILINE,
)
_SOQL_FROM_RE = re.compile(r"\bFROM\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_SOQL_SELECT_BLOCK_RE = re.compile(
    r"\bSELECT\b(?P<fields>.*?)\bFROM\s+(?P<object>[A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE | re.DOTALL,
)


def _extract_annotations(annotation_block: str) -> list[str]:
    return _ANNOTATION_NAME_RE.findall(annotation_block or "")


def _extract_soql_selected_fields(text: str) -> list[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for match in _SOQL_SELECT_BLOCK_RE.finditer(text):
        object_name = match.group("object")
        raw_fields = match.group("fields")
        for raw_field in raw_fields.split(","):
            token = " ".join(raw_field.split())
            if not token:
                continue
            # Drop aliases/extra clauses and only keep canonical field token.
            field_name = token.split()[0]
            if "(" in field_name or ")" in field_name:
                continue
            if field_name == "COUNT":
                continue
            pairs.add((object_name, field_name))
    return sorted(pairs)


def index_apex_class(path: str, conn: sqlite3.Connection) -> None:
    """
    Parse an Apex .cls file and populate the db.
    """
    text = Path(path).read_text(encoding="utf-8")

    class_match = _CLASS_RE.search(text)
    if class_match is None:
        return
    class_name = class_match.group(1)

    sharing_match = _SHARING_RE.search(text)
    sharing_model = sharing_match.group(0).lower() if sharing_match else None

    class_prefix = text[: class_match.start()]
    class_annotations = _extract_annotations(class_prefix)

    conn.execute(
        """
        INSERT INTO apex_classes (class_name, file_path, sharing_model, raw_annotations)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(class_name) DO UPDATE SET
            file_path=excluded.file_path,
            sharing_model=excluded.sharing_model,
            raw_annotations=excluded.raw_annotations
        """,
        (class_name, path, sharing_model, json.dumps(class_annotations)),
    )

    # Incremental indexing: replace method rows and SOQL edges for this class.
    conn.execute("DELETE FROM apex_methods WHERE class_name = ?", (class_name,))
    conn.execute(
        """
        DELETE FROM edges
        WHERE source_type = 'apex_class'
          AND source_name = ?
          AND edge_type = 'queries'
          AND target_type = 'sobject'
        """,
        (class_name,),
    )

    for method_match in _METHOD_RE.finditer(text):
        method_name = method_match.group("name")
        return_type = method_match.group("rtype")
        modifiers = method_match.group("mods") or ""
        method_annotations = _extract_annotations(method_match.group("ann"))
        is_static = 1 if "static" in modifiers.split() else 0

        conn.execute(
            """
            INSERT INTO apex_methods (
                class_name, method_name, return_type, annotations, is_static
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (class_name, method_name, return_type, json.dumps(method_annotations), is_static),
        )

    queried_objects = {m.group(1) for m in _SOQL_FROM_RE.finditer(text)}
    for object_name in sorted(queried_objects):
        conn.execute(
            """
            INSERT INTO edges (
                source_type, source_name, edge_type, target_type, target_name
            ) VALUES ('apex_class', ?, 'queries', 'sobject', ?)
            """,
            (class_name, object_name),
        )
    conn.commit()


def index_object(path: str, conn: sqlite3.Connection) -> None:
    """
    Parse a .object-meta.xml file and populate and populate the db.
    """
    xml_text = Path(path).read_text(encoding="utf-8")
    root = etree.fromstring(xml_text.encode("utf-8"))

    ns_uri = root.nsmap.get(None)
    ns = {"m": ns_uri} if ns_uri else {}
    x = "m:" if ns else ""

    object_name = Path(path).name.replace(".object-meta.xml", "")
    label = root.findtext(f"{x}label", namespaces=ns)

    conn.execute(
        """
        INSERT INTO sobjects (object_name, label, file_path)
        VALUES (?, ?, ?)
        ON CONFLICT(object_name) DO UPDATE SET
            label=excluded.label,
            file_path=excluded.file_path
        """,
        (object_name, label, path),
    )

    # Incremental indexing: replace field rows and lookup edges for this object.
    conn.execute("DELETE FROM sobject_fields WHERE object_name = ?", (object_name,))
    conn.execute(
        """
        DELETE FROM edges
        WHERE source_type = 'sobject'
          AND source_name = ?
          AND edge_type = 'lookup_to'
          AND target_type = 'sobject'
        """,
        (object_name,),
    )

    for field_node in root.findall(f"{x}fields", namespaces=ns):
        field_name = field_node.findtext(f"{x}fullName", namespaces=ns)
        field_type = field_node.findtext(f"{x}type", namespaces=ns)
        reference_to = field_node.findtext(f"{x}referenceTo", namespaces=ns)

        if not field_name:
            continue

        conn.execute(
            """
            INSERT INTO sobject_fields (
                object_name, field_name, field_type, reference_to
            ) VALUES (?, ?, ?, ?)
            """,
            (object_name, field_name, field_type, reference_to),
        )

        if reference_to:
            conn.execute(
                """
                INSERT INTO edges (
                    source_type, source_name, edge_type, target_type, target_name
                ) VALUES ('sobject', ?, 'lookup_to', 'sobject', ?)
                """,
                (object_name, reference_to),
            )
    conn.commit()


def build_dependency_edges(conn: sqlite3.Connection) -> None:
    """
    After all files are indexed, perform any additional processing over the
    fully-populated index.
    """
    # Backfill fields from SOQL for objects with sparse metadata fixtures.
    class_rows = conn.execute(
        "SELECT file_path FROM apex_classes ORDER BY class_name"
    ).fetchall()
    for row in class_rows:
        apex_path = row["file_path"]
        try:
            text = Path(apex_path).read_text(encoding="utf-8")
        except OSError:
            continue
        for object_name, field_name in _extract_soql_selected_fields(text):
            conn.execute(
                """
                INSERT INTO sobject_fields (object_name, field_name, field_type, reference_to)
                SELECT ?, ?, NULL, NULL
                WHERE EXISTS (
                    SELECT 1 FROM sobjects WHERE object_name = ?
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM sobject_fields
                    WHERE object_name = ?
                      AND field_name = ?
                )
                """,
                (object_name, field_name, object_name, object_name, field_name),
            )

    # Keep this pass deterministic and idempotent by removing duplicate edges.
    conn.execute(
        """
        DELETE FROM edges
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM edges
            GROUP BY source_type, source_name, edge_type, target_type, target_name
        )
        """
    )
    conn.commit()
