from agents.catalog_agent import CatalogAgent
from typing import Optional

catalog = CatalogAgent()


def register(mcp):

    @mcp.tool()
    async def list_tables(search: Optional[str] = None):
        """
        List catalog tables optionally filtered by search term.
        """
        return await catalog.list_tables(search)


    @mcp.tool()
    async def get_table_details(table_name: str):
        """
        Get full metadata details for a table.
        """
        return await catalog.get_table_details(table_name)


    @mcp.tool()
    async def get_pii_tables():
        """
        Return all tables containing PII columns.
        """
        return await catalog.get_pii_tagged_tables()