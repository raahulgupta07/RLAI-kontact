# KONTACT — Catalog Vision RAG

Upload photos of product catalogs and brochures, extract structured data with AI vision agents, and chat with the knowledge.

## What it does

1. **Upload** — Take photos of catalog pages from your phone or upload image files
2. **Extract** — Multi-agent AI classifies each image and extracts structured data (products, contacts, specs, diagrams)
3. **Search** — Full-text and semantic search across all extracted data
4. **Chat** — Ask questions and get answers with source citations

## Quick Start

### Docker (recommended)

```bash
cp .env.example .env
# Add your OpenRouter API key to .env

docker compose up -d --build
# Open http://localhost:8000
```

### Manual

```bash
# Backend
pip3 install -r requirements.txt

# Frontend
cd frontend && npm install && npm run build && cd ..

# Run
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## How it works

```
Phone/Browser                    Backend
─────────────                    ───────
Take photo      ──► Upload ──►  Queue (instant, no wait)
                                  │
              Later...            ▼
                    Process ──►  Classifier Agent ──► "product_page"
                                  │
                                  ▼
                              Specialized Agent ──► Structured JSON
                                  │
                                  ▼
                              SQLite + ChromaDB (indexed)
                                  │
Ask question    ──► Chat ───►  RAG (semantic + FTS5 search)
                                  │
                                  ▼
                              Answer + Sources
```

## 8 Extraction Agents

| Agent | What it extracts |
|-------|-----------------|
| Product Page | Product names, models, specs, categories, prices |
| Company Profile | Description, factory details, certifications |
| Cover | Company name, taglines, trade show info |
| Contact Page | Person, phone, email, website, addresses |
| Tech Diagram | Systems, zones, architecture, features |
| Section Divider | Section titles and numbers |
| Price List | Items with prices, units, currency |
| Other | General text and key info |

## API

| Endpoint | Purpose |
|----------|---------|
| `POST /api/upload` | Upload images to queue |
| `POST /api/process` | Run extraction on pending items |
| `GET /api/queue/batches` | View all batches and progress |
| `POST /api/chat` | Ask questions (RAG) |
| `GET /api/search?q=` | Full-text search |
| `GET /api/search/semantic?q=` | Semantic search |
| `GET /api/data` | Browse all extracted data |
| `GET /api/export/json` | Export as JSON |
| `GET /api/export/csv` | Export as CSV |

## Tech Stack

- **Backend**: FastAPI + Python 3.12
- **AI**: Claude Sonnet via OpenRouter
- **Database**: SQLite (WAL) + FTS5
- **Vectors**: ChromaDB + sentence-transformers
- **Frontend**: SvelteKit 5 + Tailwind v4
- **Design**: Brutalist (same as City-Dash)
- **Deploy**: Docker (multi-stage build)

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `OPENROUTER_API_KEY` | Yes | openrouter.ai/keys |

## Project Structure

```
City-KONTACT/
├── main.py              # FastAPI (18 endpoints + SPA serving)
├── chat.py              # RAG chain
├── database.py          # SQLite + FTS5 + queue + chat history
├── vectorstore.py       # ChromaDB embeddings
├── config.py            # Configuration
├── pipeline/
│   ├── loader.py        # Image processing
│   ├── extractor.py     # Multi-agent extraction
│   └── agents.py        # 8 specialized prompts
├── frontend/            # SvelteKit 5 (mobile-first)
├── Dockerfile
└── docker-compose.yml
```

## Built by City AI Team
