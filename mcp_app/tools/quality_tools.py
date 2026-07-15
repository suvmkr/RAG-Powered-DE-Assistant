# mcp_app/tools/quality_tools.py

from mcp.server.fastmcp import FastMCP
from agents.quality_agent import QualityAgent
from loguru import logger

qa = QualityAgent()


def register(mcp: FastMCP):

    @mcp.tool()
    def run_quality_check(
        pipeline_name: str,
        run_id: str = None,
    ):
        """
        Run data quality checks on a pipeline.
        """

        try:

            logger.info(
                f"[MCP] Running quality check "
                f"pipeline={pipeline_name}"
            )

            result = qa.run_check(
                pipeline_name,
                run_id,
            )

            return {
                "status": "success",
                "pipeline": pipeline_name,
                "report": result,
            }

        except Exception as e:

            logger.exception(
                "[MCP] Quality check failed"
            )

            return {
                "status": "error",
                "pipeline": pipeline_name,
                "error": str(e),
            }