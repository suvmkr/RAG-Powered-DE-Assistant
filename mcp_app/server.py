from mcp.server.fastmcp import FastMCP

from mcp_app.tools.retrieval_tools import register as register_retrieval
from mcp_app.tools.monitoring_tools import register as register_monitoring
from mcp_app.tools.quality_tools import register as register_quality
from mcp_app.tools.catalog_tools import register as register_catalog

mcp = FastMCP("rag-de-assistant")

register_retrieval(mcp)
register_monitoring(mcp)
register_quality(mcp)
register_catalog(mcp)   

if __name__ == "__main__":
    mcp.run()