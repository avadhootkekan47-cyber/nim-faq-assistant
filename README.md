# NIM FAQ Assistant

> AI-powered FAQ bot + general assistant demo backed by **NVIDIA NIM** (OpenAI-compatible inference API).

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Features

| Feature | Details |
|---|---|
| 📚 FAQ Bot | TF-IDF semantic search over a YAML knowledge base |
| 💬 General Chat | Multi-turn conversation powered by NIM |
| 🔀 Hybrid Mode | FAQ context injected into NIM prompts automatically |
| 🔗 Webhook Connector | Generic HTTP connector for Slack / email / Zapier integration |
| 🐳 Docker | Full Docker Compose setup for local + cloud |
| ⚡ Retry Logic | Auto-retry on 429 / 5xx with exponential backoff |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (HTML)                  │
│          FAQ Bot │ General Chat │ Hybrid Mode       │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP
┌───────────────────────▼─────────────────────────────┐
│                  FastAPI Backend                    │
│                                                     │
│  POST /api/faq-ask   POST /api/chat   GET /health   │
│  POST /connector/webhook                            │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  FAQ Engine │  │  NIM Client  │  │  Sessions │  │
│  │  (TF-IDF)  │  │  (httpx +    │  │  (memory) │  │
│  │  faq.yml   │  │   tenacity)  │  │           │  │
│  └─────────────┘  └──────┬───────┘  └───────────┘  │
└─────────────────────────-│───────────────────────────┘
                           │ HTTPS
                  ┌────────▼────────┐
                  │  NVIDIA NIM API │
                  │  (OpenAI-compat)│
                  └─────────────────┘
```

---

## Requirements

- Python **3.10+** (3.12 recommended)
- A valid **NVIDIA NIM API key** → [build.nvidia.com](https://build.nvidia.com)
- Docker + Docker Compose (optional, for containerised run)
- GitHub CLI `gh` (optional, for one-command repo publish)

---

## Quick Start (Local, No Docker)

### 1. Clone the repo

```bash
git clone https://github.com/avadhootkekan47-cyber/nim-faq-assistant.git
cd nim-faq-assistant
```

### 2. Set up the backend

```bash
bash scripts/dev_setup.sh
```

This creates a `.venv`, installs dependencies, and copies `.env.example` → `.env`.

### 3. Configure your NIM key

Open `backend/.env` and set:

```env
NIM_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
NIM_MODEL=meta/llama-3.1-8b-instruct   # or any NIM-available model
NIM_BASE_URL=https://integrate.api.nvidia.com/v1
```

> **Find available models** at [build.nvidia.com/explore/reasoning](https://build.nvidia.com/explore/reasoning)

### 4. Run the backend

```bash
bash scripts/run_local.sh
```

Backend is live at **http://localhost:8000**
Auto-generated API docs: **http://localhost:8000/docs**

### 5. Open the frontend

Just open `frontend/index.html` in your browser — no build step needed.

---

## Docker Compose (Local + Cloud)

```bash
# 1. Copy and fill in your .env
cp backend/.env.example backend/.env
# Edit backend/.env with your NIM_API_KEY

# 2. Build and start
docker compose up --build

# Backend → http://localhost:8000
# Frontend → http://localhost:3000
```

To run in the background:
```bash
docker compose up -d
docker compose logs -f
```

---

## API Reference

### `GET /health`
```json
{ "status": "ok", "faq_count": 22, "active_sessions": 3 }
```

### `POST /api/faq-ask`
```json
// Request
{
  "question": "How much does the Pro plan cost?",
  "mode": "hybrid",        // "hybrid" | "faq-only"
  "top_k": 3               // optional, default from env
}

// Response
{
  "answer": "The Pro plan costs $29/month...",
  "matched_faqs": [
    { "id": "pricing-001", "question": "...", "category": "pricing" }
  ],
  "mode": "hybrid"
}
```

### `POST /api/chat`
```json
// Request
{
  "message": "Can you explain rate limits?",
  "session_id": null,              // null = new session
  "mode": "faq-aware"              // "assistant" | "faq-aware"
}

// Response
{
  "reply": "Sure! Rate limits are...",
  "session_id": "uuid-here"        // pass this back to continue the conversation
}
```

### `POST /connector/webhook`
```json
// Request (from Slack, email processor, etc.)
{
  "text": "What is the refund policy?",
  "session_id": null,
  "source": "slack"
}

// Response
{
  "reply": "We offer a 30-day money-back guarantee...",
  "session_id": "uuid-here",
  "source": "slack"
}
```

---

## Configuring NIM

All NIM settings live in `backend/.env`:

| Variable | Default | Description |
|---|---|---|
| `NIM_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NIM API base URL |
| `NIM_API_KEY` | *(required)* | Your NVIDIA NIM API key |
| `NIM_MODEL` | `meta/llama-3.1-8b-instruct` | Model identifier |
| `LLM_TEMPERATURE` | `0.3` | Sampling temperature |
| `LLM_MAX_TOKENS` | `512` | Max tokens per response |
| `LLM_TOP_P` | `0.95` | Top-p nucleus sampling |
| `LLM_TIMEOUT` | `30` | Request timeout (seconds) |
| `LLM_MAX_RETRIES` | `3` | Retries on 429/5xx |

---

## Adding / Editing FAQs

Edit `backend/faq_data/faq.yml`. Each entry:

```yaml
- id: my-faq-001          # unique ID
  category: pricing        # pricing | account | technical | troubleshooting | integrations
  tags: [pricing, cost]    # used for search
  question: How much does it cost?
  answer: >
    It costs $29/month for the Pro plan.
```

Restart the backend (or it picks up on next Docker build) to reload.

> **Switching to a database:** Replace `_load_from_yaml()` in `backend/src/faq/loader.py`
> with a DB query. The `FAQStore` interface stays the same.

---

## Adding Connectors

The `backend/src/connectors/` directory is where new channel adapters live.

**To add a Slack connector:**
1. Create `backend/src/connectors/slack.py`
2. Define an `APIRouter` with a `/connector/slack/events` POST endpoint
3. Parse Slack's Events API payload → extract `event.text`
4. Call `nim_client.chat()` or reuse the chat route logic
5. Mount in `main.py`: `app.include_router(slack_router)`

Same pattern for email, Telegram, Discord, WhatsApp (via Twilio), etc.

---

## Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

---

## Project Structure

```
nim-faq-assistant/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── pyproject.toml             # Python dependencies
│   ├── .env.example               # Env var template
│   ├── faq_data/
│   │   └── faq.yml                # FAQ knowledge base (edit me!)
│   ├── src/
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── faq/
│   │   │   └── loader.py          # FAQ loader + TF-IDF search
│   │   ├── llm/
│   │   │   └── nim_client.py      # NIM API client (httpx + tenacity)
│   │   ├── routes/
│   │   │   └── api.py             # Route handlers
│   │   ├── session/
│   │   │   └── store.py           # In-memory session store
│   │   └── connectors/
│   │       └── webhook.py         # Generic webhook connector
│   └── tests/
│       └── test_faq.py            # FAQ loader tests
├── frontend/
│   └── index.html                 # Single-page chat UI (no build step)
├── infra/
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
├── scripts/
│   ├── dev_setup.sh               # One-time setup
│   └── run_local.sh               # Start local dev server
├── docker-compose.yml
├── .gitignore
├── LICENSE
└── README.md
```

---

## Deployment (Cloud)

For cloud deployment (Railway, Render, Fly.io, GCP Cloud Run):

1. Build and push the backend image:
   ```bash
   docker build -f infra/Dockerfile.backend -t nim-backend ./backend
   ```

2. Set environment variables in your cloud provider's dashboard (same as `.env`).

3. The frontend `index.html` can be served from any static host (Vercel, Netlify, GitHub Pages) — just update the **Backend URL** field in the UI config panel.

---

## License

MIT © 2025 avadhootkekan47-cyber
