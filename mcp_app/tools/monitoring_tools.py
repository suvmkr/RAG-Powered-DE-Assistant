# mcp_app/tools/monitoring_tools.py

from mcp.server.fastmcp import FastMCP

from monitoring.health_checker import HealthChecker
from monitoring.sla_tracker import SLATracker
from monitoring.failure_logs import FailureLogs

hc = HealthChecker()

sla = SLATracker()

failures = FailureLogs()


def register(mcp: FastMCP):

    @mcp.tool()
    def get_pipeline_health():

        return hc.get_full_report()

    @mcp.tool()
    def get_sla_report(
        days: int = 7,
    ):

        return sla.get_report(days)

    @mcp.tool()
    def get_recent_failures(
        limit: int = 20,
    ):

        return failures.get_recent(limit)