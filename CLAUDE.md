# CLAUDE.md

## Project Overview

KONTACT is a **catalog vision RAG system** — upload photos of product brochures/catalogs from your phone, extract structured data using multi-agent AI vision, and chat with the extracted knowledge. Built for trade show attendees who photograph vendor catalogs and need instant searchable intelligence.

**Architecture**: Images → Queue → Classifier Agent → Specialized Extractor Agent → SQLite + ChromaDB → RAG Chatbot

```
Phone Camera → Upload API (queue) → Batch Process → Multi-Agent Vision → SQLite + FTS5 + ChromaDB → Chat RAG
```

## Structure

```
City-KONTACT/
├── main.py                    # FastAPI entry (18 endpoints, CORS, SPA serving)
├── config.py                  # OpenRouter API config, model selection, paths
├── chat.py                    # RAG chain (semantic + FTS5 retrieval → context → LLM)
├── database.py                # SQLite + FTS5 + queue + chat history (WAL mode)
├── vectorstore.py             # ChromaDB + sentence-transformers (all-MiniLM-L6-v2)
├── .env                       # OPENROUTER_API_KEY
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Multi-stage: Node frontend + Python backend
├── docker-compose.yml         # Single service, persistent volume
├── .dockerignore
├── pipeline/
│   ├── __init__.py
│   ├── loader.py              # Image → base64 (resize to 4096px max, JPEG 90%)
│   ├── extractor.py           # Multi-agent extraction (classifier → specialized agent)
│   └── agents.py              # 8 specialized extraction prompts
├── data/
│   ├── kontact.db             # SQLite database (WAL mode)
│   ├── chroma/                # ChromaDB persistent vector store
│   ├── extractions/           # JSON output files per folder
│   └── uploads/               # Uploaded image batches
└── frontend/                  # SvelteKit 5 + Tailwind v4
    ├── package.json
    ├── svelte.config.js       # Static adapter, SPA fallback
    ├── vite.config.ts         # Tailwind v4 plugin, API proxy to :8000
    ├── tsconfig.json
    ├── build/                 # Production build (served by FastAPI)
    └── src/
        ├── app.html           # Mobile viewport, Space Grotesk font
        ├── app.css            # Brutalist design system (mobile-first)
        ├── app.d.ts
        ├── lib/
        │   └── api.ts         # 17 typed API functions
        └── routes/
            ├── +layout.svelte # Bottom nav (4 tabs), theme toggle
            ├── +layout.ts     # SPA mode (no SSR)
            ├── +page.svelte   # Redirect → /upload
            ├── upload/        # Camera/gallery upload with thumbnails
            ├── queue/         # Batch cards, progress bars, CLI terminal
            ├── chat/          # RAG chatbot with sessions, sources, suggestions
            ├── more/          # Search, export, stats, re-index
            └── data/          # Browse extracted docs as expandable cards
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `documents` | Extracted data per image (folder, file, type, company, products, contact, raw_text, full_json) |
| `documents_fts` | FTS5 virtual table for full-text search across all extracted text |
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

**8 Specialized Agents:**

| Agent | Extracts |
|-------|----------|
| `product_page` | Products: name, model, specs, category, price, image_desc |
| `company_profile` | Company: description, established, location, factory, certifications, services |
| `cover` | Cover: company, title, taglines, trade show info, contact |
| `contact_page` | Contact: person, phone, email, website, address, global offices |
| `tech_diagram` | Systems: name, zone, description, features, architecture |
| `section_divider` | Section: title, number, minimal content |
| `price_list` | Items: name, model, price, unit, specs, currency |
| `other` | General: key info, raw text |

## Upload → Queue → Process Flow

```
1. UPLOAD (instant, no processing)
   POST /api/upload         → save files to disk, add to queue table
   POST /api/upload/folder  → queue from local folder path

2. QUEUE CHECK
   GET /api/queue           → status counts (pending/done/error)
   GET /api/queue/batches   → all batches with progress

3. PROCESS (triggered manually or in background)
   POST /api/process        → run extraction on pending items (blocking)
   POST /api/process/background → run async (returns immediately)

   Per image: classify → route to agent → extract → save to SQLite + ChromaDB
```

## RAG Chat Pipeline

```
User Question
  ↓
ChromaDB semantic search (top 5 nearest vectors)
  +
SQLite FTS5 text search (keyword match, top 3)
  ↓
Deduplicate + merge context chunks (max 8)
  ↓
Build messages: system prompt + chat history (last 6) + context + question
  ↓
Claude Sonnet via OpenRouter → answer
  ↓
Save to chat_history (session persistence)
  ↓
Return { answer, sources: [{folder, file, company}], session_id }
```

## API Endpoints (18)

### Upload & Queue
```
POST   /api/upload              # Upload images → queue (instant, FormData)
POST   /api/upload/folder       # Queue from local folder path
GET    /api/queue               # Queue status (optional ?batch_id=)
GET    /api/queue/batches       # All batches overview
GET    /api/queue/pending       # Pending items list
POST   /api/process             # Process pending queue (blocking)
POST   /api/process/background  # Process async in background
```

### Search
```
GET    /api/search?q=           # FTS5 full-text search
GET    /api/search/semantic?q=  # ChromaDB vector search
```

### Data
```
GET    /api/data                # All documents (optional ?folder=)
GET    /api/stats               # Summary stats
POST   /api/index               # Re-index all JSONs into DB + vectors
```

### Chat
```
POST   /api/chat                # RAG chat (json: {question, session_id?})
GET    /api/chat/sessions       # List all chat sessions
GET    /api/chat/history/{id}   # Get session messages
DELETE /api/chat/sessions/{id}  # Delete a session
```

### Export
```
GET    /api/export/json         # Download all data as JSON
GET    /api/export/csv          # Download all data as CSV
```

### Health
```
GET    /health                  # Health check
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Python 3.12 |
| LLM | Claude Sonnet via OpenRouter |
| Database | SQLite (WAL mode) + FTS5 |
| Vectors | ChromaDB (persistent, local) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Image Processing | Pillow (resize, JPEG conversion) |
| Frontend | SvelteKit 5 + Svelte 5 runes |
| CSS | Tailwind v4 + Brutalist design system |
| Font | Space Grotesk (monospace) |
| Deploy | Docker (multi-stage build) |

## Frontend Design

**Brutalist/Retro aesthetic (same as City-Dash):**
- No border-radius (global reset `border-radius: 0px !important`)
- Stamp shadows (hard 4px drop shadow)
- Ink borders (asymmetric 2px top/left, 4px bottom/right)
- Uppercase typography with letter-spacing
- Space Grotesk monospace font
- Dark mode support via CSS variables

**Mobile-first:**
- Bottom navigation (4 tabs in thumb zone, 56px height)
- Camera-first upload (`capture="environment"`)
- 48px minimum touch targets
- Single column layout, no sidebars
- Swipeable thumbnail strips
- Sticky chat input
- Expandable cards instead of tables
- Safe area padding for notches

## Configuration

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `OPENROUTER_API_KEY` | Yes | — | Get from openrouter.ai/keys |
| `VISION_MODEL` | No | `anthropic/claude-sonnet-4` | Vision-capable model |
| `MAX_WORKERS` | No | `8` | Parallel extraction workers |

## Commands

```bash
# Development
pip3 install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Docker
docker compose up -d --build
# Open http://localhost:8000

# Frontend dev (with hot reload)
cd frontend && npm run dev
# Proxies /api to localhost:8000
```

## Key Design Decisions

1. **Queue-based processing** — Upload is instant (save to disk + queue table). Processing happens separately. Designed for phone users who upload quickly and process later.
2. **Multi-agent extraction** — Classifier detects image type first, then routes to specialized agent with type-specific schema. Better accuracy than single generic prompt.
3. **Dual search** — FTS5 for exact keyword matches + ChromaDB for semantic similarity. RAG combines both for best context retrieval.
4. **SQLite over PostgreSQL** — Single-file database, no server needed, WAL mode for concurrent reads. Sufficient for single-user/small-team use.
5. **SPA frontend** — SvelteKit with static adapter, served by FastAPI. Single Docker container, no nginx needed.
6. **OpenRouter** — Unified LLM proxy. Easy to switch models without code changes.
