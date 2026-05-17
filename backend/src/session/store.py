"""
src/session/store.py
────────────────────
In-memory conversation session store.
Each session tracks the message history for multi-turn chat.

TODO: Replace InMemorySessionStore with a Redis / Postgres-backed version
      by implementing the same SessionStore interface below.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from src.llm.nim_client import Message


# ── Domain types ──────────────────────────────────────────────────────────────

@dataclass
class Session:
    id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self.updated_at = time.time()

    def truncated_messages(self, max_turns: int = 20) -> list[Message]:
        """Keep the system message + last max_turns messages to limit context."""
        msgs = self.messages
        system = [m for m in msgs if m["role"] == "system"]
        non_system = [m for m in msgs if m["role"] != "system"]
        return system + non_system[-(max_turns * 2):]


# ── Interface (for future DB implementations) ─────────────────────────────────

class SessionStore(Protocol):
    def create(self, system_prompt: str) -> Session: ...
    def get(self, session_id: str) -> Session | None: ...
    def save(self, session: Session) -> None: ...
    def delete(self, session_id: str) -> None: ...


# ── In-memory implementation ──────────────────────────────────────────────────

class InMemorySessionStore:
    """
    Stores sessions in a plain dict.
    Not persistent across restarts — good enough for demos and dev.
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self, system_prompt: str = "") -> Session:
        session = Session(id=str(uuid.uuid4()))
        if system_prompt:
            session.add("system", system_prompt)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def save(self, session: Session) -> None:
        self._sessions[session.id] = session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def count(self) -> int:
        return len(self._sessions)


# ── Module-level singleton ─────────────────────────────────────────────────────
session_store = InMemorySessionStore()
