"""
src/routes/api.py
─────────────────
FastAPI route handlers.

POST /api/faq-ask   — FAQ retrieval + NIM-augmented answer
POST /api/chat      — Multi-turn general assistant (optionally FAQ-aware)
GET  /health        — Health check for load balancers / Docker
"""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.faq.loader import faq_store
from src.llm.nim_client import NIMError, nim_client
from src.session.store import session_store

logger = logging.getLogger(__name__)
router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class FAQAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    mode: Literal["faq-only", "hybrid"] = "hybrid"
    top_k: Optional[int] = Field(None, ge=1, le=10)


class FAQAskResponse(BaseModel):
    answer: str
    matched_faqs: list[dict]
    mode: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    mode: Literal["assistant", "faq-aware"] = "assistant"
    system_prompt: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class HealthResponse(BaseModel):
    status: str
    faq_count: int
    active_sessions: int


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health():
    return {
        "status": "ok",
        "faq_count": len(faq_store.all_items()),
        "active_sessions": session_store.count(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/faq-ask
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/faq-ask", response_model=FAQAskResponse)
async def faq_ask(req: FAQAskRequest):
    """
    1. Search FAQ store for relevant entries.
    2. In 'faq-only' mode: return the best FAQ answer directly.
    3. In 'hybrid' mode: pass the FAQ context to NIM and let it compose a response.
    """
    matches = faq_store.search(req.question, top_k=req.top_k)
    matched_faqs = [
        {"id": m.id, "question": m.question, "category": m.category}
        for m in matches
    ]

    # ── faq-only: return the top match answer without LLM ─────────────────────
    if req.mode == "faq-only":
        if not matches:
            return FAQAskResponse(
                answer="I couldn't find a relevant FAQ entry. Please try rephrasing your question.",
                matched_faqs=[],
                mode="faq-only",
            )
        return FAQAskResponse(
            answer=matches[0].answer,
            matched_faqs=matched_faqs,
            mode="faq-only",
        )

    # ── hybrid: compose context + ask NIM ─────────────────────────────────────
    if matches:
        faq_context = "\n\n".join(
            f"Q: {m.question}\nA: {m.answer}" for m in matches
        )
        system_msg = (
            "You are a helpful support assistant. Use the FAQ context below "
            "to answer the user's question accurately and concisely. "
            "If the FAQ context is insufficient, say so honestly.\n\n"
            f"=== FAQ Context ===\n{faq_context}"
        )
    else:
        system_msg = (
            "You are a helpful support assistant. "
            "No specific FAQ entry was found for this question. "
            "Answer as best you can, and recommend the user contact support if needed."
        )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": req.question},
    ]

    try:
        answer = await nim_client.chat(messages)
    except NIMError as e:
        logger.error("NIM error in faq_ask: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM service error: {e.detail}")

    return FAQAskResponse(answer=answer, matched_faqs=matched_faqs, mode="hybrid")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/chat
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_SYSTEM = (
    "You are a knowledgeable, friendly AI assistant. "
    "Answer questions clearly and concisely. "
    "If you are unsure, say so rather than guessing."
)

_FAQ_AWARE_SYSTEM = (
    "You are a helpful support assistant with access to a company FAQ. "
    "When relevant FAQ knowledge is found, incorporate it. "
    "Always be accurate and concise."
)


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Multi-turn chat endpoint.
    - Creates or resumes a session identified by session_id.
    - In 'faq-aware' mode, prepends matching FAQ context to each user message.
    """
    # ── Get or create session ──────────────────────────────────────────────────
    session = None
    if req.session_id:
        session = session_store.get(req.session_id)

    if session is None:
        system = req.system_prompt or (
            _FAQ_AWARE_SYSTEM if req.mode == "faq-aware" else _DEFAULT_SYSTEM
        )
        session = session_store.create(system_prompt=system)

    # ── Optionally augment message with FAQ context ────────────────────────────
    user_content = req.message
    if req.mode == "faq-aware":
        matches = faq_store.search(req.message, top_k=2)
        if matches:
            faq_snippet = "\n".join(
                f"[FAQ] Q: {m.question} → A: {m.answer}" for m in matches
            )
            user_content = f"{faq_snippet}\n\nUser question: {req.message}"

    session.add("user", user_content)

    # ── Call NIM ───────────────────────────────────────────────────────────────
    try:
        reply = await nim_client.chat(session.truncated_messages())
    except NIMError as e:
        logger.error("NIM error in chat: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM service error: {e.detail}")

    session.add("assistant", reply)
    session_store.save(session)

    return ChatResponse(reply=reply, session_id=session.id)
