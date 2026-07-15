# mcp_app/tools/retrieval_tools.py

from mcp.server.fastmcp import FastMCP
from rag.retriever import Retriever

retriever = Retriever()


def register(mcp: FastMCP):

    @mcp.tool()
    def retrieve(
        question: str,
        mode: str = "code",
        k: int = 6,
    ):
        """
        Retrieve relevant context from ChromaDB.
        """

        if mode == "catalog":
            collection = "data_catalog"
        elif mode == "health":
            collection = "pipeline_docs"
        else:
            collection = "pipeline_code"

        docs = retriever.query(
            question=question,
            collection=collection,
            k=k,
        )

        return docs

    @mcp.tool()
    def retrieve_all(
        question: str,
        k: int = 6,
    ):
        """
        Query all collections.
        """

        return retriever.query_all(
            question=question,
            k=k,
        )
