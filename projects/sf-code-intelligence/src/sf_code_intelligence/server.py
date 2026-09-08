"""
server.py – Exposes query.py functions as MCP tools.
Run with: python -m sf_code_intelligence.server
"""

from mcp.server.fastmcp import FastMCP

from sf_code_intelligence import query
from sf_code_intelligence.db import get_connection, init_db

mcp = FastMCP("sf-code-intelligence")
_conn = None


def get_conn():
    global _conn
    if _conn is None:
        init_db()
        _conn = get_connection()
    return _conn


@mcp.tool()
def search_symbol(name: str) -> list[dict]:
    """Search for Apex classes or methods by name."""
    return query.search_symbol(name, get_conn())


@mcp.tool()
def get_object_schema(object_name: str) -> dict:
    """Get field schema for a Salesforce object."""
    return query.get_object_schema(object_name, get_conn())


@mcp.tool()
def find_apex_touching_object(object_name: str) -> list[dict]:
    """Find all Apex classes that reference a given SObject."""
    return query.find_apex_touching_object(object_name, get_conn())


@mcp.tool()
def get_class_summary(class_name: str) -> dict:
    """Get a token-efficient summary of an Apex class."""
    return query.get_class_summary(class_name, get_conn())


if __name__ == "__main__":
    mcp.run()
