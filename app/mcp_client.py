from pathlib import Path
from contextlib import AsyncExitStack

from loguru import logger

from mcp.client.session import ClientSession
from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters,
)


class DEAssistantMCPClient:

    def __init__(self):

        self.session = None

        self.exit_stack = AsyncExitStack()

    async def connect(self):

        logger.info("[MCP] Starting MCP session")

        # Project root
        project_root = (
            Path(__file__)
            .resolve()
            .parent.parent
        )

        server_params = StdioServerParameters(

            command="python3",

            args=[
                "-m",
                "mcp_app.server",
            ],

            cwd=str(project_root),
        )

        read_stream, write_stream = (
            await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
        )

        self.session = (
            await self.exit_stack.enter_async_context(
                ClientSession(
                    read_stream,
                    write_stream,
                )
            )
        )

        await self.session.initialize()
        tools = await self.session.list_tools()

        print("\n=== MCP TOOLS ===")
        for t in tools.tools:
            print(t.name)
        print("=================\n")
        logger.info(
            "[MCP] MCP session initialized"
        )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
    ):

        import json

        result = await self.session.call_tool(
            tool_name,
            arguments=arguments,
        )

        # MCP returns structured content
        if hasattr(result, "content"):

            parsed = []

            for item in result.content:

                if hasattr(item, "text"):

                    text = item.text

                    # Try parsing JSON
                    try:
                        parsed.append(
                            json.loads(text)
                        )

                    except Exception:

                        parsed.append(text)

            if len(parsed) == 1:
                return parsed[0]

            return parsed

        return result

    async def disconnect(self):

        logger.info("[MCP] Closing MCP session")

        await self.exit_stack.aclose()


mcp_client = DEAssistantMCPClient()