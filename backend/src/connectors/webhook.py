"""
src/connectors/webhook.py
─────────────────────────
Example connector: a simple HTTP webhook that forwards inbound POST payloads
to the /api/chat endpoint internally.

Any external system (Slack, email processor, Zapier, etc.) can POST to
POST /connector/webhook with JSON:
  {
    "text": "user message here",
    "session_id": "optional-session-id",
    "source": "slack" | "email" | "custom"
  }

The connector normalises the payload, calls the chat logic, and returns:
  {
    "reply": "assistant reply",
    "session_id": "...",
    "source": "..."
  }

── How to add a new connector ────────────────────────────────────────────────
1. Create src/connectors/<name>.py
2. Define an APIRouter and implement your normalise_in / normalise_out logic.
3. Mount it in main.py: app.include_router(your_router)

Examples you might build:
  - SlackConnector: parse Slack Events API payloads, respond via Slack SDK.
  - EmailConnector: receive inbound email webhook, reply via SMTP/SendGrid.
  - TelegramConnector: handle Telegram Bot API updates.
  - DiscordConnector: handle Discord interactions.
"""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.llm.nim_client import NIMError, nim_client
from src.session.store import session_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connector", tags=["connectors"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class WebhookRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000, description="User message")
    session_id: Optional[str] = None
    source: str = Field("webhook", description="Name of the calling system")
    mode: Literal["assistant", "faq-aware"] = "assistant"


class WebhookResponse(BaseModel):
    reply: str
    session_id: str
    source: str


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/webhook", response_model=WebhookResponse)
async def webhook(req: WebhookRequest):
    """
    Generic webhook connector. Receives a message from any external system,
    processes it through the NIM assistant, and returns the reply.
    """
    logger.info("Webhook message from source=%s session=%s", req.source, req.session_id)

    # Get or create session
    session = None
    if req.session_id:
        session = session_store.get(req.session_id)
    if session is None:
        session = session_store.create(
            system_prompt=(
                "You are a helpful AI assistant answering questions via an "
                f"external integration ({req.source}). Be concise."
            )
        )

    session.add("user", req.text)

    try:
        reply = await nim_client.chat(session.truncated_messages())
    except NIMError as e:
        logger.error("NIM error in webhook connector: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    session.add("assistant", reply)
    session_store.save(session)

    return WebhookResponse(reply=reply, session_id=session.id, source=req.source)
