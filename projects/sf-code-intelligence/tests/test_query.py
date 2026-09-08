import json

import pytest

import sf_code_intelligence.db as db
from sf_code_intelligence import query
from sf_code_intelligence.db import get_connection, init_db
from sf_code_intelligence.indexer import (
    build_dependency_edges,
    index_apex_class,
    index_object,
)

FIXTURES = "fixtures"


@pytest.fixture
def conn(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setenv("SF_INDEX_DB", test_db)
    db.DB_PATH = test_db
    init_db()
    c = get_connection()
    for f in [
        "PropertyController",
        "GeocodingService",
        "FileUtilities",
        "SampleDataController",
        "PagedResult",
        "ListingService",
    ]:
        index_apex_class(f"{FIXTURES}/classes/{f}.cls", c)
    index_object(f"{FIXTURES}/objects/Property__c/Property__c.object-meta.xml", c)
    index_object(f"{FIXTURES}/objects/Broker__c/Broker__c.object-meta.xml", c)
    index_object(f"{FIXTURES}/objects/Listing__c/Listing__c.object-meta.xml", c)
    build_dependency_edges(c)
    c.commit()
    yield c
    c.close()


def test_search_symbol_finds_class(conn):
    results = query.search_symbol("PropertyController", conn)
    assert any(r["class_name"] == "PropertyController" for r in results)


def test_search_symbol_finds_method(conn):
    results = query.search_symbol("getPagedPropertyList", conn)
    assert len(results) > 0


def test_get_object_schema_returns_fields(conn):
    result = query.get_object_schema("Property__c", conn)
    assert "fields" in result
    assert len(result["fields"]) > 0
    assert "file_path" not in result


def test_get_object_schema_not_found(conn):
    result = query.get_object_schema("NonExistent__c", conn)
    assert result.get("error") == "not found"


def test_find_apex_touching_object_uses_edges(conn):
    results = query.find_apex_touching_object("Property__c", conn)
    class_names = [r["class_name"] for r in results]
    assert "PropertyController" in class_names


def test_find_apex_touching_listing_uses_edges(conn):
    results = query.find_apex_touching_object("Listing__c", conn)
    class_names = [r["class_name"] for r in results]
    assert "ListingService" in class_names


def test_get_object_schema_listing_includes_lookup(conn):
    result = query.get_object_schema("Listing__c", conn)
    assert "fields" in result
    names = {f["name"] for f in result["fields"]}
    assert "Broker__c" in names
    assert "Price__c" in names
    assert result.get("relationship_count", 0) >= 1


def test_get_class_summary_shape(conn):
    result = query.get_class_summary("PropertyController", conn)
    assert "methods" in result
    assert "objects_queried" in result
    assert "aura_enabled_count" in result
    assert len(json.dumps(result)) < 3000


def test_search_symbol_blank_returns_empty(conn):
    assert query.search_symbol("   ", conn) == []


def test_search_symbol_exact_class_ranked_first(conn):
    conn.execute(
        """
        INSERT INTO apex_classes (class_name, file_path, sharing_model, raw_annotations)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(class_name) DO NOTHING
        """,
        ("PropertyControllerHelper", "fixtures/classes/PropertyController.cls", None, "[]"),
    )
    conn.commit()
    results = query.search_symbol("PropertyController", conn)
    assert results[0]["type"] == "class"
    assert results[0]["class_name"] == "PropertyController"


def test_find_apex_touching_object_deduplicates_duplicate_edges(conn):
    conn.execute(
        """
        INSERT INTO edges (source_type, source_name, edge_type, target_type, target_name)
        VALUES ('apex_class', 'PropertyController', 'queries', 'sobject', 'Property__c')
        """
    )
    conn.commit()
    results = query.find_apex_touching_object("Property__c", conn)
    property_rows = [row for row in results if row["class_name"] == "PropertyController"]
    assert len(property_rows) == 1


def test_get_class_summary_not_found(conn):
    assert query.get_class_summary("MissingController", conn) == {"error": "not found"}


def test_find_apex_touching_object_payload_is_token_efficient(conn):
    result = query.find_apex_touching_object("Property__c", conn)
    assert len(json.dumps(result)) < 2000
