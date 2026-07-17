"""
pipeline_agent.py  –  Core conversational agent.
Receives retrieved context, builds Groq messages, streams response.
"""

from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional

from groq import Groq
from loguru import logger

from app.config import get_settings
from rag.prompt_templates import (
    DE_ASSISTANT_SYSTEM,
    RAG_USER_TEMPLATE,
    HEALTH_SUMMARY_SYSTEM,
    HEALTH_SUMMARY_USER,
    CATALOG_SYSTEM,
)
from rag.retriever import Retriever

cfg = get_settings()


class PipelineAgent:
    """
    Wraps the Groq Chat Completions API with:
    - Context injection from retrieved docs
    - Multi-turn history
    - Mode-specific system prompts
    - Token budget management
    """

    MODE_SYSTEM_PROMPTS = {
        "code": DE_ASSISTANT_SYSTEM,
        "catalog": CATALOG_SYSTEM,
        "health": HEALTH_SUMMARY_SYSTEM,
        "auto": DE_ASSISTANT_SYSTEM,
    }

    def __init__(self):
        self._client = Groq(api_key=cfg.groq_api_key)
        self._retriever = Retriever()

    async def answer(
        self,
        question: str,
        retrieved_docs: List[Dict[str, Any]],
        history: List[Dict[str, str]] | None = None,
        mode: str = "auto",
        extra_context: Optional[Any] = None,
    ) -> str:
        """
        Generate an answer using Groq with RAG context.
        Runs in asyncio via run_in_executor to keep the event loop free.
        """
        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            None,
            self._sync_answer,
            question,
            retrieved_docs,
            history,
            mode,
            extra_context,
        )

    def _sync_answer(
        self,
        question: str,
        retrieved_docs: List[Dict[str, Any]],
        history: List[Dict[str, str]] | None,
        mode: str,
        extra_context: Optional[Any],
    ) -> str:

        system_prompt = self.MODE_SYSTEM_PROMPTS.get(
            mode,
            DE_ASSISTANT_SYSTEM,
        )

        context = self._retriever.format_context(
            retrieved_docs,
            max_tokens=cfg.max_context_tokens // 2,
        )

        if extra_context:
            import json
            context += (
                f"\n\n## Live Monitoring Data\n"
                f"{json.dumps(extra_context, indent=2)}"
            )

        user_content = RAG_USER_TEMPLATE.format(
            context=context,
            question=question,
        )

        messages = self._build_messages(
            history or [],
            user_content,
            system_prompt,
        )

        logger.debug(
            f"[PipelineAgent] Calling Groq with "
            f"{len(messages)} messages, mode={mode}"
        )

        try:
            response = self._client.chat.completions.create(
                model=cfg.llm_model,
                messages=messages,
                temperature=0.2,
                max_tokens=1500,
            )

            answer = response.choices[0].message.content

            logger.debug(
                f"[PipelineAgent] Received {len(answer)} chars"
            )

            return answer

        except Exception as e:
            logger.error(f"[PipelineAgent] Groq API error: {e}")

            return (
                f"⚠️ Sorry, I encountered an API error:\n\n{str(e)}"
            )

    def _build_messages(
        self,
        history: List[Dict[str, str]],
        current_user_message: str,
        system_prompt: str,
    ) -> List[Dict[str, str]]:
        """
        Build the messages array for Groq.
        Keep last 6 turns of history.
        """

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]

        for turn in history[-6:]:

            role = turn.get("role", "user")
            content = turn.get("content", "")

            if role in ("user", "assistant") and content:
                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        messages.append(
            {
                "role": "user",
                "content": current_user_message,
            }
        )

        return messages