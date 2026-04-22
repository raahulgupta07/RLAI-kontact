# CLAUDE.md

## Project Overview

KONTACT is a **catalog vision RAG agent** — upload photos of product brochures/catalogs, extract structured data using multi-agent AI vision, and chat with an intelligent agent that can run SQL queries, remember facts, and cite sources with catalog images. Built for trade show attendees who photograph vendor catalogs and need instant searchable intelligence.

**Architecture**: Images → Queue → Classifier Agent → Specialized Extractor → SQLite + ChromaDB → Chat Agent (RAG + SQL Tools + Memory)

```
Phone Camera → Upload API (auto-queue) → Batch Process → Multi-Agent Vision → SQLite + FTS5 + ChromaDB → Agent (RAG + SQL + Memory)
```

## Structure

```
City-KONTACT/
├── main.py                    # FastAPI entry (20+ endpoints, SSE streaming, CORS, SPA serving)
├── config.py                  # Env-based config (OpenRouter API, models, paths)
├── chat.py                    # Agent with RAG + SQL tool loop + memory injection
├── tools.py                   # SQL tool, schema introspect, catalog summary
├── memory.py                  # Feedback storage + memories + learning context builder
├── database.py                # SQLite + FTS5 + queue + chat history (WAL mode)
├── vectorstore.py             # ChromaDB + OpenRouter embeddings (OpenAI text-embedding-3-small)
├── .env                       # OPENROUTER_API_KEY + optional overrides
├── .env.example               # Configuration template
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Multi-stage: Node frontend + Python backend + healthcheck
├── docker-compose.yml         # Single service, persistent volume, healthcheck
├── deploy.sh                  # One-command build + start
├── .dockerignore
├── .gitignore
├── pipeline/
│   ├── __init__.py
│   ├── loader.py              # Image → base64 (resize to 4096px max, JPEG 90%)
│   ├── extractor.py           # Async batch extraction (classifier → specialized agent)
│   └── agents.py              # 8 specialized extraction prompts
├── data/
│   ├── kontact.db             # SQLite database (WAL mode)
│   ├── chroma/                # ChromaDB persistent vector store
│   ├── extractions/           # JSON output files per batch
│   ├── uploads/               # Uploaded image batches (portable)
│   ├── feedback.json          # Thumbs up/down feedback
│   └── memories.json          # Agent memories
└── frontend/                  # SvelteKit 5 + Tailwind v4
    ├── package.json
    ├── svelte.config.js       # Static adapter, SPA fallback
    ├── vite.config.ts         # Tailwind v4 plugin, API proxy to :8000
    ├── static/
    │   ├── manifest.json      # PWA manifest
    │   ├── sw.js              # Service worker (network-first)
    │   └── icon.svg           # App icon
    └── src/
        ├── app.html           # Mobile viewport, Space Grotesk font, PWA registration
        ├── app.css            # Brutalist design system (mobile-first, focus indicators)
        ├── lib/
        │   ├── api.ts         # Typed API client functions
        │   └── markdown.ts    # Markdown → HTML (tables, code blocks, lists, copy button)
        └── routes/
            ├── +layout.svelte # Desktop sidebar + mobile bottom nav (5 tabs)
            ├── +layout.ts     # SPA mode (no SSR)
            ├── +page.svelte   # Redirect → /upload
            ├── upload/        # Camera/gallery upload, drag-drop, quality warnings
            ├── queue/         # Batch list, inline expand with thumbnails, retry, terminal
            ├── chat/          # Agent chat: streaming SSE, SQL tools, citations, history, voice
            ├── data/          # Document browser: filter, sort, expand, copy/save, timestamps
            └── more/          # Search, export, stats, models, re-index
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `documents` | Extracted data per image (folder, file, type, company, products JSON, contact JSON, raw_text) |
| `documents_fts` | FTS5 virtual table for full-text search |
| `queue` | Upload queue (batch_id, file_name, file_path, status, image_type, error) |
| `chat_history` | Conversation persistence (session_id, role, content, timestamp) |

## Multi-Agent Pipeline

**2-step extraction per image:**

```
Step 1: CLASSIFIER AGENT
  Input:  Image (base64)
  Output: { image_type, confidence }
  Types:  product_page | company_profile | cover | contact_page | tech_diagram | section_divider | price_list | other

Step 2: SPECIALIZED AGENT (routed by classifier)
  Input:  Image + type-specific prompt
  Output: Structured JSON with type-specific schema
```

## Chat Agent Architecture

```
User Question
  ↓
Build Context:
  ├─ ChromaDB semantic search (top 5 vectors)
  ├─ SQLite FTS5 search (keyword match, top 3)
  └─ Deduplicate + merge (max 8 chunks)
  ↓
Build System Prompt:
  ├─ Base instructions (tool descriptions, guidelines)
  ├─ Learning context (memories, approved/rejected feedback, catalog summary)
  └─ Available tools: query_catalog_db, introspect_schema, get_catalog_summary
  ↓
First LLM Call (buffered, not streamed)
  ↓
Tool Loop (up to 3 iterations):
  ├─ Parse [TOOL: name]...[/TOOL] markers
  ├─ Execute tools (SQL, schema, summary)
  ├─ Send results back to LLM
  └─ Get refined answer
  ↓
Stream Clean Answer (SSE events: session, status, content, done)
  ↓
Save to chat_history + return sources with image URLs
```

## SQL Tools

| Tool | Purpose |
|------|---------|
| `query_catalog_db(sql)` | Read-only SQL against kontact.db, returns markdown table, max 50 rows |
| `introspect_schema(table)` | List tables or show columns/types/samples for a table |
| `get_catalog_summary()` | Overview: total docs, products, companies, folders, categories |

## Memory System

| Storage | File | Purpose |
|---------|------|---------|
| Memories | `data/memories.json` | Agent facts persisted across sessions |
| Feedback | `data/feedback.json` | Thumbs up/down with question/answer pairs |

**Learning context injected into every agent prompt:**
1. AGENT MEMORIES — facts from memories.json
2. APPROVED RESPONSES — thumbs-up examples
3. AVOID THESE PATTERNS — thumbs-down examples
4. CATALOG SUMMARY — live stats from get_catalog_summary()

## API Endpoints (20+)

### Upload & Queue
```
POST   /api/upload              # Upload images (auto-processes in background)
POST   /api/upload/folder       # Queue from local folder path
GET    /api/queue               # Queue status
GET    /api/queue/batches       # All batches overview
GET    /api/queue/pending       # Pending items
GET    /api/queue/errors        # Errored items
POST   /api/queue/retry/{id}    # Retry failed item
POST   /api/process             # Process queue (blocking)
POST   /api/process/background  # Process async
```

### Chat & Agent
```
POST   /api/chat                # RAG chat with SQL tools
POST   /api/chat/stream         # Streaming chat via SSE
GET    /api/chat/sessions       # List sessions with previews
GET    /api/chat/history/{id}   # Get session messages
DELETE /api/chat/sessions/{id}  # Delete session
```

### Search
```
GET    /api/search?q=           # FTS5 full-text search
GET    /api/search/semantic?q=  # ChromaDB vector search
```

### Data & Export
```
GET    /api/data                # All documents (optional ?folder=)
GET    /api/stats               # Summary stats
POST   /api/index               # Re-index all JSONs into DB + vectors
GET    /api/export/json         # Export as JSON
GET    /api/export/csv          # Export as CSV
```

### Feedback & Memory
```
POST   /api/feedback            # Save thumbs up/down
GET    /api/memories            # List agent memories
```

### Other
```
GET    /api/image/{folder}/{f}  # Serve catalog images (path traversal protected)
GET    /api/config              # Model configuration
GET    /health                  # Health check (Docker)
```

## Frontend UI Features

**Chat (Agent Page)**
- Streaming SSE with RAG ANALYZING animation (spinner + checkmarks)
- CLI execution bar: `$ kontact exec --catalog-rag --gemini...`
- Tool steps in terminal style (Running query_catalog_db... ✓ 0.01s)
- Image citations as clickable thumbnails with lightbox
- Action bar: HELPFUL? thumbs + COPY + SAVE
- Follow-up suggestion chips
- User avatar + timestamps + READ/AGENT labels
- Voice input (Web Speech API)
- Session history sidebar with search + time ago
- Export conversation as markdown
- 60s stream timeout protection

**Queue Page**
- Compact list rows with status icons (checkmark/spinner)
- Inline EXPAND showing document thumbnails + metadata
- Skeleton loading for images
- RETRY / RETRY ALL for failed items
- Compact terminal log (last 8 lines)

**Data Browser**
- Filter by folder + image type
- Sort: newest, oldest, by type, company, folder
- Expandable cards with thumbnails, products, contacts
- COPY text + SAVE JSON buttons
- Timestamps on every card

**Upload Page**
- Camera capture + drag-drop + gallery select
- Real upload progress bar (XMLHttpRequest)
- Image quality warnings (< 200px or < 10KB)
- Error banner on upload failure
- Custom batch naming

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Python 3.12 |
| LLM | Gemini 3.1 Flash Lite via OpenRouter |
| Embeddings | OpenAI text-embedding-3-small via OpenRouter |
| Database | SQLite (WAL mode) + FTS5 |
| Vectors | ChromaDB (persistent, local) |
| Frontend | SvelteKit 5 + Svelte 5 runes |
| CSS | Tailwind v4 + Brutalist design system |
| Font | Space Grotesk (monospace) |
| Deploy | Docker (multi-stage build, healthcheck) |
| PWA | manifest.json + service worker (network-first) |

## Configuration

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `OPENROUTER_API_KEY` | Yes | — | Get from openrouter.ai/keys |
| `VISION_MODEL` | No | `google/gemini-3.1-flash-lite-preview` | Vision-capable model |
| `EMBEDDING_MODEL` | No | `openai/text-embedding-3-small` | Embedding model |
| `MAX_WORKERS` | No | `8` | Parallel extraction workers |
| `PORT` | No | `8000` | Server port |

## Commands

```bash
# Development
pip3 install -r requirements.txt
pip3 install chromadb sentence-transformers
cd frontend && npm install && npm run build && cd ..
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Docker
cp .env.example .env  # add OPENROUTER_API_KEY
./deploy.sh
# Open http://localhost:8000

# Frontend dev (with hot reload)
cd frontend && npm run dev
# Proxies /api to localhost:8000
```

## Key Design Decisions

1. **Queue-based processing** — Upload instant, process later. Auto-process in background.
2. **Multi-agent extraction** — Classifier detects image type, routes to specialized agent.
3. **Dual search** — FTS5 for keywords + ChromaDB for semantic similarity.
4. **SQL tool agent** — Precise counting/filtering/aggregation via tool loop.
5. **Prompt-based tool calling** — `[TOOL:]...[/TOOL]` markers instead of native tool_use (OpenRouter compatibility).
6. **File-based memory** — JSON files for feedback/memories (no extra DB needed).
7. **Network-first SW** — PWA service worker always fetches from network first.
8. **Portable images** — All images in `data/uploads/`, no external path dependencies.
