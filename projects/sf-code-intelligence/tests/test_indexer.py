import pytest

import sf_code_intelligence.db as db
from sf_code_intelligence.db import get_connection, init_db
from sf_code_intelligence.indexer import (
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
    yield c
    c.close()


def test_apex_class_indexed(conn):
    index_apex_class(f"{FIXTURES}/classes/PropertyController.cls", conn)
    row = conn.execute(
        "SELECT * FROM apex_classes WHERE class_name = 'PropertyController'"
    ).fetchone()
    assert row is not None, "PropertyController should be indexed"


def test_apex_methods_indexed(conn):
    index_apex_class(f"{FIXTURES}/classes/PropertyController.cls", conn)
    methods = conn.execute(
        "SELECT * FROM apex_methods WHERE class_name = 'PropertyController'"
    ).fetchall()
    assert len(methods) > 0, "PropertyController should have at least one method"


def test_aura_enabled_annotation_captured(conn):
    index_apex_class(f"{FIXTURES}/classes/PropertyController.cls", conn)
    methods = conn.execute(
        "SELECT * FROM apex_methods WHERE class_name = 'PropertyController' "
        "AND annotations LIKE '%AuraEnabled%'"
    ).fetchall()
    assert len(methods) > 0, "At least one method should be @AuraEnabled"


def test_soql_edge_created(conn):
    index_apex_class(f"{FIXTURES}/classes/PropertyController.cls", conn)
    edges = conn.execute(
        "SELECT * FROM edges WHERE source_name = 'PropertyController' "
        "AND edge_type = 'queries'"
    ).fetchall()
    assert len(edges) > 0, "PropertyController queries at least one SObject"


def test_listing_service_soql_edges(conn):
    index_apex_class(f"{FIXTURES}/classes/ListingService.cls", conn)
    edges = conn.execute(
        "SELECT * FROM edges WHERE source_name = 'ListingService' "
        "AND edge_type = 'queries' AND target_name = 'Listing__c'"
    ).fetchall()
    assert len(edges) > 0, "ListingService should declare a SOQL edge to Listing__c"


def test_object_indexed(conn):
    index_object(f"{FIXTURES}/objects/Property__c/Property__c.object-meta.xml", conn)
    row = conn.execute(
        "SELECT * FROM sobjects WHERE object_name = 'Property__c'"
    ).fetchone()
    assert row is not None


def test_object_fields_indexed(conn):
    # Listing__c.object-meta.xml embeds fields; Property__c fixture intentionally does not.
    index_object(f"{FIXTURES}/objects/Listing__c/Listing__c.object-meta.xml", conn)
    fields = conn.execute(
        "SELECT * FROM sobject_fields WHERE object_name = 'Listing__c'"
    ).fetchall()
    assert len(fields) >= 2, "Listing__c should expose Broker__c lookup and Price__c"


def test_lookup_field_creates_edge(conn):
    index_object(f"{FIXTURES}/objects/Listing__c/Listing__c.object-meta.xml", conn)
    edges = conn.execute(
        "SELECT * FROM edges WHERE source_name = 'Listing__c' "
        "AND edge_type = 'lookup_to' AND target_name = 'Broker__c'"
    ).fetchall()
    assert len(edges) > 0, "Listing__c should have a lookup edge to Broker__c"
