# KONTACT — Catalog Vision RAG Agent

Upload photos of product catalogs and brochures, extract structured data with AI vision agents, and chat with an intelligent catalog agent that can run SQL queries, remember facts, and cite sources with images.

## Features

**Upload & Extract**
- Mobile-first camera upload with drag-and-drop
- 8 specialized AI extraction agents (products, contacts, tech diagrams, price lists, etc.)
- Queue-based processing with real-time progress
- Image quality warnings before upload
- Retry failed extractions

**Intelligent Chat Agent**
- Streaming responses (SSE) with RAG ANALYZING animation
- SQL tool — agent runs queries for precise counts, filtering, aggregation
- Memory system — learns from feedback (thumbs up/down)
- Image citations — catalog page thumbnails inline with responses
- Lightbox — click citations to view full-size source pages
- Voice input (Web Speech API)
- Export conversations as markdown
- Session history with search

**Data Browser**
- Filter by folder, type, company
- Sort by date, type, company
- Expandable cards with products, contacts, key info
- Copy/Save JSON per document
- Inline thumbnails

**Search**
- Full-text search (FTS5)
- Semantic vector search (ChromaDB + OpenAI embeddings)
- Dual search with merged results

**Export**
- JSON export (all data)
- CSV export (flat table)
- Chat export (markdown)

## Quick Start

### Docker (recommended)

```bash
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

./deploy.sh
# Open http://localhost:8000
```

### Manual

```bash
# Backend
pip3 install -r requirements.txt
pip3 install chromadb sentence-transformers

# Frontend
cd frontend && npm install && npm run build && cd ..

# Run
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Architecture

```
Phone/Browser                      Backend
─────────────                      ───────
Take photo      ──► Upload ──►    Queue (instant, auto-process in background)
                                    │
                                    ▼
                    Classify ──►  Classifier Agent → "product_page"
                                    │
                                    ▼
                    Extract  ──►  Specialized Agent → Structured JSON
                                    │
                                    ▼
                                  SQLite + ChromaDB (indexed)
                                    │
Ask question    ──► Agent  ──►   RAG (semantic + FTS5) + SQL Tools + Memory
                                    │
                                    ▼
                                  Streaming Answer + Image Citations
```

## Agent Capabilities

| Capability | How |
|-----------|-----|
| **Count & aggregate** | SQL tool: `SELECT COUNT(*) FROM documents` |
| **Filter & compare** | SQL tool: `SELECT * FROM documents WHERE company = 'Ahua'` |
| **Search products** | RAG: semantic + keyword search across all catalogs |
| **Inspect schema** | Schema tool: lists tables, columns, sample data |
| **Remember facts** | Memory system: saves/recalls facts across sessions |
| **Learn from feedback** | Thumbs up/down → improves future responses |
| **Cite sources** | Image citations with clickable thumbnails |

## 8 Extraction Agents

| Agent | What it extracts |
|-------|-----------------|
| Product Page | Product names, models, specs, categories, prices, image descriptions |
| Company Profile | Description, factory details, certifications, services |
| Cover | Company name, taglines, trade show info |
| Contact Page | Person, phone, email, website, addresses, global offices |
| Tech Diagram | Systems, zones, architecture, features |
| Section Divider | Section titles and numbers |
| Price List | Items with prices, units, currency |
| Other | General text and key info |

## API Endpoints (20+)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/upload` | Upload images (auto-processes in background) |
| `POST /api/process` | Manually process pending items |
| `GET /api/queue/batches` | View all batches with progress |
| `POST /api/queue/retry/{id}` | Retry failed extraction |
| `POST /api/chat/stream` | Streaming chat with SQL tools (SSE) |
| `POST /api/chat` | Non-streaming chat |
| `GET /api/chat/sessions` | List chat sessions with previews |
| `GET /api/search?q=` | Full-text search |
| `GET /api/search/semantic?q=` | Semantic vector search |
| `GET /api/data` | Browse extracted documents |
| `GET /api/image/{folder}/{file}` | Serve catalog images |
| `GET /api/export/json` | Export all data as JSON |
| `GET /api/export/csv` | Export as CSV |
| `POST /api/feedback` | Save thumbs up/down feedback |
| `GET /api/memories` | View agent memories |
| `GET /api/config` | Model configuration |
| `GET /health` | Health check |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Python 3.12 |
| LLM | Gemini 3.1 Flash Lite via OpenRouter |
| Embeddings | OpenAI text-embedding-3-small via OpenRouter |
| Database | SQLite (WAL mode) + FTS5 full-text search |
| Vectors | ChromaDB (persistent, local) |
| Frontend | SvelteKit 5 + Tailwind v4 |
| Design | Brutalist (Space Grotesk, no border-radius, ink borders) |
| Deploy | Docker (multi-stage build) |
| PWA | Installable, network-first caching |

## Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `OPENROUTER_API_KEY` | Yes | — |
| `VISION_MODEL` | No | `google/gemini-3.1-flash-lite-preview` |
| `EMBEDDING_MODEL` | No | `openai/text-embedding-3-small` |
| `MAX_WORKERS` | No | `8` |
| `PORT` | No | `8000` |

## Project Structure

```
City-KONTACT/
├── main.py              # FastAPI (20+ endpoints, SSE streaming, SPA)
├── chat.py              # RAG agent with SQL tool loop + memory
├── tools.py             # SQL tool, schema introspect, catalog summary
├── memory.py            # Feedback + memories (JSON file-based)
├── database.py          # SQLite + FTS5 + queue + chat history
├── vectorstore.py       # ChromaDB + OpenRouter embeddings
├── config.py            # Environment-based configuration
├── pipeline/
│   ├── loader.py        # Image loading + preprocessing
│   ├── extractor.py     # Async batch extraction
│   └── agents.py        # 8 specialized extraction prompts
├── frontend/
│   └── src/routes/
│       ├── upload/      # Camera/gallery upload
│       ├── queue/       # Batch management + inline expand
│       ├── chat/        # Agent chat (streaming, citations, history)
│       ├── data/        # Document browser (filter, sort, export)
│       └── more/        # Search, export, stats, models
├── data/
│   ├── uploads/         # Uploaded images (portable)
│   ├── extractions/     # JSON extraction results
│   ├── chroma/          # Vector store
│   └── kontact.db       # SQLite database
├── Dockerfile           # Multi-stage (Node + Python)
├── docker-compose.yml   # Production-ready with healthcheck
├── deploy.sh            # One-command deployment
└── .env.example         # Configuration template
```

## Screenshots

**Chat Agent** — Streaming responses with SQL tools, image citations, CLI execution bar

**Queue** — Batch management with inline document expand, thumbnails, retry

**Data Browser** — Filter/sort documents, expandable cards with products and contacts

**Upload** — Mobile camera capture, drag-drop, image quality warnings

## License

MIT

## Built by RLAI Team
