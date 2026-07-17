"""
api.py  –  FastAPI backend exposing REST endpoints consumed by the
           Streamlit frontend and external clients.

MCP-enabled architecture:
FastAPI → MCP Client → MCP Server → Tools → Business Logic

Run:
    uvicorn app.api:app --host 0.0.0.0 --port 8502 --reload
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import (
    FastAPI,
    Depends,
    BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger

from app.config import get_settings
from app.auth import (
    create_session,
    require_auth,
)
from app.mcp_client import mcp_client
from agents.pipeline_agent import PipelineAgent

cfg = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="RAG-Powered DE Assistant API",
    description=(
        "Conversational assistant for Data Engineers "
        "with MCP-based tool orchestration."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# MCP Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():

    logger.info("[API] Starting MCP client")

    await mcp_client.connect()

    logger.info("[API] MCP client connected")


@app.on_event("shutdown")
async def shutdown_event():

    logger.info("[API] Closing MCP client")

    await mcp_client.disconnect()

    logger.info("[API] MCP client disconnected")


# ─────────────────────────────────────────────────────────────────────────────
# Lazy Agent Singleton
# ─────────────────────────────────────────────────────────────────────────────

_pipeline_agent: Optional[PipelineAgent] = None


def get_pipeline_agent() -> PipelineAgent:

    global _pipeline_agent

    if _pipeline_agent is None:
        _pipeline_agent = PipelineAgent()

    return _pipeline_agent


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )

    mode: str = Field(
        "auto",
        pattern="^(auto|code|catalog|health)$",
    )

    history: List[Dict[str, str]] = Field(
        default_factory=list
    )


class ChatResponse(BaseModel):

    answer: str

    sources: List[Dict[str, Any]] = []

    mode_used: str

    latency_ms: float

    agent_actions: List[str] = []


class QualityCheckRequest(BaseModel):

    pipeline_name: str

    run_id: Optional[str] = None


class TokenResponse(BaseModel):

    token: str

    expires_in_seconds: int = 28800


# ─────────────────────────────────────────────────────────────────────────────
# Auth Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/auth/token",
    response_model=TokenResponse,
    tags=["Auth"],
)
async def get_token(
    user: str = "de-user",
):

    """
    Issue a session token.
    Replace with OAuth/JWT in production.
    """

    token = create_session(user)

    return TokenResponse(token=token)


# ─────────────────────────────────────────────────────────────────────────────
# Core Chat Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/chat",
    response_model=ChatResponse,
    tags=["Chat"],
)
async def chat(
    req: ChatRequest,
    session: dict = Depends(require_auth),
):

    t0 = time.time()

    question = req.question.strip()

    agent_actions: List[str] = []

    health_summary = None

    # ─────────────────────────────────────────────────────────────────────
    # Route Question
    # ─────────────────────────────────────────────────────────────────────

    mode = req.mode

    if mode == "auto":
        mode = _classify_question(question)

    logger.info(
        f"[chat] "
        f"user={session['user']} "
        f"mode={mode} "
        f"q={question[:100]}"
    )

    # ─────────────────────────────────────────────────────────────────────
    # MCP Retrieval
    # ─────────────────────────────────────────────────────────────────────

    if mode in ["code", "catalog", "health"]:

        docs = await mcp_client.call_tool(
            "retrieve",
            {
                "question": question,
                "mode": mode,
                "k": cfg.top_k,
            },
        )

        agent_actions.append(
            f"MCP.retrieve(mode={mode})"
        )

    else:

        docs = await mcp_client.call_tool(
            "retrieve_all",
            {
                "question": question,
                "k": cfg.top_k,
            },
        )

        agent_actions.append(
            "MCP.retrieve_all()"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Health Context
    # ─────────────────────────────────────────────────────────────────────

    if mode == "health":

        health_summary = await mcp_client.call_tool(
            "get_pipeline_health",
            {},
        )

        agent_actions.append(
            "MCP.get_pipeline_health()"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Generate Final Answer
    # ─────────────────────────────────────────────────────────────────────

    p_agent = get_pipeline_agent()

    answer = await p_agent.answer(
        question=question,
        retrieved_docs=docs,
        history=req.history,
        extra_context=health_summary,
    )

    # ─────────────────────────────────────────────────────────────────────
    # Source Formatting
    # ─────────────────────────────────────────────────────────────────────

    sources = []

    for d in docs:

        sources.append({
            "id": d.get("id", ""),
            "source": (
                d.get("metadata", {})
                .get("source", "unknown")
            ),
            "score": round(
                d.get("score", 0.0),
                4,
            ),
            "preview": (
                d.get("document", "")[:200]
            ),
        })

    return ChatResponse(
        answer=answer,
        sources=sources,
        mode_used=mode,
        latency_ms=round(
            (time.time() - t0) * 1000,
            1,
        ),
        agent_actions=agent_actions,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Quality Check Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/agents/quality-check",
    tags=["Agents"],
)
async def trigger_quality_check(
    req: QualityCheckRequest,
    background_tasks: BackgroundTasks,
    session: dict = Depends(require_auth),
):

    """
    Trigger asynchronous quality checks through MCP.
    """

    async def _run():

        await mcp_client.call_tool(
            "run_quality_check",
            {
                "pipeline_name": req.pipeline_name,
                "run_id": req.run_id,
            },
        )

    background_tasks.add_task(_run)

    logger.info(
        f"[quality-check] "
        f"pipeline={req.pipeline_name} "
        f"run={req.run_id}"
    )

    return {
        "status": "queued",
        "pipeline": req.pipeline_name,
        "message": (
            f"Quality check queued "
            f"for '{req.pipeline_name}'."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Catalog Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/catalog/tables",
    tags=["Catalog"],
)
async def list_tables(
    search: Optional[str] = None,
    session: dict = Depends(require_auth),
):

    return await mcp_client.call_tool(
        "list_tables",
        {
            "search": search,
        },
    )


@app.get(
    "/catalog/tables/{table_name}",
    tags=["Catalog"],
)
async def get_table_info(
    table_name: str,
    session: dict = Depends(require_auth),
):

    return await mcp_client.call_tool(
        "get_table_details",
        {
            "table_name": table_name,
        },
    )


@app.get(
    "/catalog/pii",
    tags=["Catalog"],
)
async def get_pii_tables(
    session: dict = Depends(require_auth),
):

    return await mcp_client.call_tool(
        "get_pii_tables",
        {},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Monitoring Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/monitoring/health",
    tags=["Monitoring"],
)
async def pipeline_health(
    session: dict = Depends(require_auth),
):

    return await mcp_client.call_tool(
        "get_pipeline_health",
        {},
    )


@app.get(
    "/monitoring/sla",
    tags=["Monitoring"],
)
async def sla_report(
    days: int = 7,
    session: dict = Depends(require_auth),
):

    return await mcp_client.call_tool(
        "get_sla_report",
        {
            "days": days,
        },
    )


@app.get(
    "/monitoring/failures",
    tags=["Monitoring"],
)
async def recent_failures(
    limit: int = 20,
    session: dict = Depends(require_auth),
):

    return await mcp_client.call_tool(
        "get_recent_failures",
        {
            "limit": limit,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/ingest/trigger",
    tags=["Ingestion"],
)
async def trigger_ingestion(
    background_tasks: BackgroundTasks,
    session: dict = Depends(require_auth),
):

    """
    Re-index all data into ChromaDB.
    """

    from ingestion.metadata_ingest import MetadataIngestor
    from ingestion.code_parser import CodeParser
    from ingestion.docs_loader import DocsLoader

    async def _run():

        DocsLoader().ingest()

        CodeParser().ingest()

        MetadataIngestor().ingest()

    background_tasks.add_task(_run)

    return {
        "status": "ingestion_started",
        "message": (
            "Ingestion triggered successfully."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Health Ping
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/ping",
    tags=["Infra"],
)
async def ping():

    return {
        "status": "ok",
        "model": cfg.llm_model,
        "mcp_enabled": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _classify_question(
    q: str,
) -> str:

    """
    Simple heuristic router.
    Replace with LLM router later.
    """

    q_lower = q.lower()

    if any(
        k in q_lower
        for k in [
            "schema",
            "table",
            "column",
            "pii",
            "lineage",
            "catalog",
            "dataset",
        ]
    ):
        return "catalog"

    if any(
        k in q_lower
        for k in [
            "fail",
            "slo",
            "sla",
            "health",
            "status",
            "alert",
            "broken",
            "lag",
        ]
    ):
        return "health"

    if any(
        k in q_lower
        for k in [
            "code",
            "function",
            "class",
            "import",
            "pipeline",
            "dag",
            "task",
            "logic",
            "def ",
        ]
    ):
        return "code"

    return "code"