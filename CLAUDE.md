# CLAUDE.md

## Project Overview

KONTACT is a **catalog vision RAG agent** — snap photos of product catalogs at trade shows, extract structured data with multi-agent AI vision, and chat with an intelligent agent that runs SQL queries, remembers facts, cites sources with images, and knows who you met. Built for trade show attendees who need instant searchable intelligence from vendor catalogs.

**Architecture**: Phone Camera → Upload → Classifier → Specialized Extractor → Normalized DB (documents + products + contacts with UUIDs) → Agent (RAG + SQL Tools + Memory)

## Structure

```
City-KONTACT/
├── main.py                    # FastAPI entry (25+ endpoints, SSE streaming, CORS, SPA)
├── config.py                  # Env-based config (models, API keys, paths)
├── chat.py                    # Agent: RAG + SQL tool loop + memory + personality
├── tools.py                   # SQL tool, schema introspect, catalog summary
├── memory.py                  # Feedback (thumbs up/down) + memories (JSON files)
├── database.py                # SQLite + FTS5 + normalized tables + UUIDs + metadata
├── vectorstore.py             # ChromaDB + OpenRouter embeddings
├── pipeline/
│   ├── loader.py              # Image + PDF loading + EXIF metadata extraction (GPS, camera, date)
│   ├── extractor.py           # Async batch extraction (classifier → specialized agent)
│   └── agents.py              # 8 specialized extraction prompts
├── data/
│   ├── kontact.db             # SQLite (documents + products + contacts + queue + chat_history)
│   ├── chroma/                # ChromaDB persistent vector store
│   ├── extractions/           # JSON output files per batch
│   ├── uploads/               # Uploaded image batches (portable)
│   ├── feedback.json          # Thumbs up/down feedback
│   └── memories.json          # Agent memories
├── frontend/src/
│   ├── app.css                # Brutalist design system (Space Grotesk, focus indicators)
│   ├── lib/
│   │   ├── api.ts             # Typed API client
│   │   └── markdown.ts        # Markdown → HTML (tables, code blocks, copy)
│   └── routes/
│       ├── +layout.svelte     # Desktop sidebar + mobile bottom nav (5 tabs)
│       ├── upload/            # Camera/PDF upload, quality warnings, EXIF extraction
│       ├── queue/             # Batch list, inline expand, retry, delete, toast, terminal
│       ├── chat/              # Agent: streaming SSE, SQL tools, citations, feedback, voice
│       ├── data/              # Document browser: metadata tags, filter, sort, expand, copy/save
│       └── more/              # 7 tables + gallery + search + export + stats
├── Dockerfile                 # Multi-stage (Node + Python + healthcheck)
├── docker-compose.yml         # Production-ready with health + volumes
├── deploy.sh                  # One-command build + start
└── .env.example               # Configuration template
```

## Database Schema (6 tables)

```sql
-- Core tables
documents          -- 36 rows, one per catalog page
  id, uuid, folder, source_file, image_type, company, title,
  products (JSON), contact (JSON), key_info (JSON), raw_text, full_json,
  gps_lat, gps_lng, date_taken, camera_make, camera_model,
  img_width, img_height, file_size_kb, metadata (JSON), created_at

products           -- 131 rows, one per product (normalized from documents.products JSON)
  id, uuid, document_uuid, document_id, folder, source_file,
  company, name, model, specs, category, price, image_desc, created_at

contacts           -- 6 rows, one per contact (normalized from documents.contact JSON)
  id, uuid, document_uuid, document_id, folder, source_file,
  company, person, phone, email, website, address, created_at

-- Support tables
documents_fts      -- FTS5 virtual table for full-text search
queue              -- Upload processing queue (batch_id, status, error)
chat_history       -- Conversation persistence (session_id, role, content)
```

## Agent System

### Tool-calling via prompt markers (not native tool_use — OpenRouter compatible)

```
LLM outputs:     [TOOL: query_catalog_db]
                  {"sql": "SELECT company, COUNT(*) FROM products GROUP BY company"}
                  [/TOOL]

Backend parses:   _parse_tool_calls() extracts name + args
Executes:         execute_tool("query_catalog_db", {"sql": "..."})
Returns result:   [RESULT: query_catalog_db] ... [/RESULT]
Sends back:       LLM gets result, generates final answer
Max iterations:   3 tool calls per question
```

### Available tools

| Tool | Purpose |
|------|---------|
| `query_catalog_db(sql)` | Read-only SQL on kontact.db, max 50 rows, returns markdown table |
| `introspect_schema(table)` | List tables or show columns/types/samples |
| `get_catalog_summary()` | Overview: docs, products, contacts, companies, GPS count |

### Smart query examples in system prompt

```sql
-- "Who did I meet?"
SELECT company, person, phone, email FROM contacts

-- "Where was this photographed?"
SELECT folder, source_file, gps_lat, gps_lng FROM documents WHERE gps_lat IS NOT NULL

-- "Show me everything from Ahua"
SELECT d.title, p.name, p.model, c.phone
FROM documents d
LEFT JOIN products p ON p.document_uuid = d.uuid
LEFT JOIN contacts c ON c.document_uuid = d.uuid
WHERE d.company = 'Ahua'

-- "What did I scan today?"
SELECT folder, source_file, company FROM documents WHERE date_taken LIKE '2026:04:22%'
```

### Memory system

| Storage | File | Injected as |
|---------|------|-------------|
| Memories | `data/memories.json` | "AGENT MEMORIES" in system prompt |
| Good feedback | `data/feedback.json` (rating='up') | "APPROVED RESPONSES" |
| Bad feedback | `data/feedback.json` (rating='down') | "AVOID THESE PATTERNS" |
| Catalog summary | Live from `get_catalog_summary()` | "CATALOG SUMMARY" |

## EXIF Metadata Extraction

When users upload phone photos, `extract_exif()` in `pipeline/loader.py` extracts:
- **GPS**: latitude, longitude (decimal degrees from DMS)
- **Date taken**: DateTimeOriginal or DateTime
- **Camera**: Make, Model (e.g., "Apple iPhone 15 Pro")
- **Dimensions**: width x height in pixels
- **File size**: in KB
- **Orientation**: EXIF orientation tag

Stored in flat columns on `documents` table for SQL queryability.

## API Endpoints (25+)

### Upload & Queue
```
POST   /api/upload              # Upload images/PDFs (auto-process, PDF splits to pages)
POST   /api/process/background  # Manual process trigger
GET    /api/queue/batches       # All batches with progress
POST   /api/queue/retry/{id}    # Retry failed item
DELETE /api/batch/{id}          # Delete batch + documents
```

### Chat Agent
```
POST   /api/chat/stream         # Streaming SSE (tool loop + status events)
POST   /api/chat                # Non-streaming chat
GET    /api/chat/sessions       # Sessions with first-message preview
```

### Data & Tables
```
GET    /api/data                # All documents (with metadata columns)
GET    /api/products            # Normalized products table
GET    /api/contacts            # Normalized contacts table
GET    /api/dashboard           # Stats + breakdowns
GET    /api/documents/metadata  # Documents with parsed EXIF
GET    /api/search?q=           # FTS5 search
GET    /api/search/semantic?q=  # ChromaDB vector search
```

### Export
```
GET    /api/export/xlsx         # Excel (3 sheets: Products, Contacts, Summary)
GET    /api/export/json         # JSON
GET    /api/export/csv          # CSV
```

### Feedback & Memory
```
POST   /api/feedback            # Thumbs up/down
GET    /api/memories            # Agent memories
POST   /api/migrate             # Run table normalization
```

### Other
```
GET    /api/image/{folder}/{f}  # Serve images (path traversal protected)
GET    /api/config              # Model config
GET    /health                  # Docker healthcheck
```

## Frontend Pages

| Page | Features |
|------|----------|
| **Upload** | Camera + PDF + drag-drop, real progress, quality warnings, HEIC/AVIF support |
| **Queue** | List rows, inline expand with thumbnails, retry/delete, toast, terminal |
| **Agent** | Streaming SSE, RAG ANALYZING animation, SQL tool steps, image citations, feedback, voice, export |
| **Data** | Filter/sort, expandable cards, metadata tags (UUID, dimensions, GPS, camera), copy/save |
| **More** | 7 data tables (Products, Contacts, Companies, Documents, Categories, Specs, Gallery) + search + export |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Python (2,467 lines) |
| Frontend | SvelteKit 5 + Tailwind v4 (4,649 lines) |
| LLM | Gemini 3.1 Flash Lite via OpenRouter |
| Embeddings | OpenAI text-embedding-3-small via OpenRouter |
| Database | SQLite (WAL) + FTS5 + 6 tables + UUIDs |
| Vectors | ChromaDB (persistent) |
| Deploy | Docker (multi-stage, healthcheck) |
| PWA | manifest.json + service worker (network-first) |

## Configuration

| Variable | Required | Default |
|----------|----------|---------|
| `OPENROUTER_API_KEY` | Yes | — |
| `VISION_MODEL` | No | `google/gemini-3.1-flash-lite-preview` |
| `EMBEDDING_MODEL` | No | `openai/text-embedding-3-small` |
| `MAX_WORKERS` | No | `8` |
| `PORT` | No | `8000` |

## Commands

```bash
# Development
pip3 install -r requirements.txt chromadb sentence-transformers openpyxl
cd frontend && npm install && npm run build && cd ..
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Docker
cp .env.example .env && ./deploy.sh

# Frontend dev (hot reload)
cd frontend && npm run dev    # Proxies /api to :8000
```
