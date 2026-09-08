"""
query.py – MCP-ready query functions over the indexed SQLite DB.

Each function returns a plain Python dict or list of dicts — JSON-serializable.
Keep responses token-efficient: no raw source, no redundant fields.
"""

import json
import sqlite3


def _parse_annotations(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return [value] if value else []
    if isinstance(loaded, list):
        return [str(item) for item in loaded]
    if isinstance(loaded, str):
        return [loaded]
    return []


def search_symbol(name: str, conn: sqlite3.Connection) -> list[dict]:
    """
    Search for Apex classes or methods whose name contains `name` (case-insensitive).

    Returns a list of matches, each with:
      { "type": "class"|"method", "class_name": str, "method_name": str|None,
        "annotations": list[str] }

    """
    term = (name or "").strip()
    if not term:
        return []
    like_term = f"%{term}%"

    class_rows = conn.execute(
        """
        SELECT class_name, raw_annotations
        FROM apex_classes
        WHERE lower(class_name) LIKE lower(?)
        ORDER BY
            CASE WHEN lower(class_name) = lower(?) THEN 0 ELSE 1 END,
            class_name
        """,
        (like_term, term),
    ).fetchall()

    method_rows = conn.execute(
        """
        SELECT class_name, method_name, annotations
        FROM apex_methods
        WHERE lower(method_name) LIKE lower(?)
        ORDER BY
            CASE WHEN lower(method_name) = lower(?) THEN 0 ELSE 1 END,
            method_name,
            class_name
        """,
        (like_term, term),
    ).fetchall()

    results: list[dict] = []
    for row in class_rows:
        results.append(
            {
                "type": "class",
                "class_name": row["class_name"],
                "method_name": None,
                "annotations": _parse_annotations(row["raw_annotations"]),
            }
        )

    for row in method_rows:
        results.append(
            {
                "type": "method",
                "class_name": row["class_name"],
                "method_name": row["method_name"],
                "annotations": _parse_annotations(row["annotations"]),
            }
        )

    return results


def get_object_schema(object_name: str, conn: sqlite3.Connection) -> dict:
    """
    Return a structured, token-efficient summary of a Salesforce object.

    Return shape:
      {
        "object_name": str,
        "label": str,
        "fields": [
          { "name": str, "type": str, "reference_to": str|None }
        ],
        "relationship_count": int
      }

    Return {"error": "not found"} if the object doesn't exist in the index.
    """
    row = conn.execute(
        """
        SELECT object_name, label
        FROM sobjects
        WHERE object_name = ?
        """,
        (object_name,),
    ).fetchone()
    if row is None:
        return {"error": "not found"}

    field_rows = conn.execute(
        """
        SELECT field_name, field_type, reference_to
        FROM sobject_fields
        WHERE object_name = ?
        ORDER BY field_name
        """,
        (object_name,),
    ).fetchall()

    relationship_count = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM edges
        WHERE source_type = 'sobject'
          AND source_name = ?
          AND edge_type = 'lookup_to'
          AND target_type = 'sobject'
        """,
        (object_name,),
    ).fetchone()["c"]

    return {
        "object_name": row["object_name"],
        "label": row["label"],
        "fields": [
            {
                "name": field["field_name"],
                "type": field["field_type"],
                "reference_to": field["reference_to"],
            }
            for field in field_rows
        ],
        "relationship_count": int(relationship_count),
    }


def find_apex_touching_object(object_name: str, conn: sqlite3.Connection) -> list[dict]:
    """
    Return all Apex classes that reference the given SObject.

    Return shape:
      [
        {
          "class_name": str,
          "edge_type": str,
          "aura_enabled_methods": list[str]
        }
      ]
    """
    edge_rows = conn.execute(
        """
        SELECT DISTINCT source_name AS class_name, edge_type
        FROM edges
        WHERE source_type = 'apex_class'
          AND target_type = 'sobject'
          AND target_name = ?
        ORDER BY
            CASE edge_type
                WHEN 'queries' THEN 0
                ELSE 1
            END,
            class_name
        """,
        (object_name,),
    ).fetchall()

    class_names = [row["class_name"] for row in edge_rows]
    aura_methods_by_class: dict[str, list[str]] = {}
    if class_names:
        placeholders = ",".join("?" for _ in class_names)
        aura_rows = conn.execute(
            f"""
            SELECT class_name, method_name, annotations
            FROM apex_methods
            WHERE class_name IN ({placeholders})
            ORDER BY class_name, method_name
            """,
            class_names,
        ).fetchall()
        for row in aura_rows:
            if "AuraEnabled" not in _parse_annotations(row["annotations"]):
                continue
            aura_methods_by_class.setdefault(row["class_name"], []).append(
                row["method_name"]
            )

    results: list[dict] = []
    for edge in edge_rows:
        results.append(
            {
                "class_name": edge["class_name"],
                "edge_type": edge["edge_type"],
                "aura_enabled_methods": aura_methods_by_class.get(
                    edge["class_name"], []
                ),
            }
        )

    return results


def get_class_summary(class_name: str, conn: sqlite3.Connection) -> dict:
    """
    Return a token-efficient summary of an Apex class suitable for passing to an LLM.

    Return shape:
      {
        "class_name": str,
        "sharing_model": str|None,
        "methods": [
          {
            "name": str,
            "return_type": str,
            "annotations": list[str],
            "is_static": bool
          }
        ],
        "objects_queried": list[str],
        "aura_enabled_count": int,
        "invocable_count": int
      }

    Return {"error": "not found"} if class doesn't exist.
    """
    class_row = conn.execute(
        """
        SELECT class_name, sharing_model
        FROM apex_classes
        WHERE class_name = ?
        """,
        (class_name,),
    ).fetchone()
    if class_row is None:
        return {"error": "not found"}

    method_rows = conn.execute(
        """
        SELECT method_name, return_type, annotations, is_static
        FROM apex_methods
        WHERE class_name = ?
        ORDER BY method_name
        """,
        (class_name,),
    ).fetchall()

    object_rows = conn.execute(
        """
        SELECT target_name
        FROM edges
        WHERE source_type = 'apex_class'
          AND source_name = ?
          AND edge_type = 'queries'
          AND target_type = 'sobject'
        ORDER BY target_name
        """,
        (class_name,),
    ).fetchall()

    methods = []
    aura_enabled_count = 0
    invocable_count = 0
    for method in method_rows:
        annotations = _parse_annotations(method["annotations"])
        if "AuraEnabled" in annotations:
            aura_enabled_count += 1
        if "InvocableMethod" in annotations:
            invocable_count += 1

        methods.append(
            {
                "name": method["method_name"],
                "return_type": method["return_type"],
                "annotations": annotations,
                "is_static": bool(method["is_static"]),
            }
        )

    return {
        "class_name": class_row["class_name"],
        "sharing_model": class_row["sharing_model"],
        "methods": methods,
        "objects_queried": [row["target_name"] for row in object_rows],
        "aura_enabled_count": aura_enabled_count,
        "invocable_count": invocable_count,
    }
