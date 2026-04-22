# KONTACT — Catalog Vision RAG Agent

Snap photos of product catalogs at trade shows, extract structured data with AI vision agents, and chat with an intelligent agent that runs SQL queries, remembers facts, cites sources with images, and knows who you met.

## What it does

1. **Upload** — Take photos of catalog pages (phone camera, PDF, drag-drop) with EXIF metadata extraction (GPS, camera, date)
2. **Extract** — 8 specialized AI agents classify and extract products, contacts, specs, prices, diagrams
3. **Normalize** — Products and contacts stored in separate queryable tables with UUIDs
4. **Chat** — Intelligent agent with SQL tools, memory, streaming, and image citations
5. **Browse** — Data tables with filters, sort, search, metadata, and Excel export

## Quick Start

```bash
# Docker (recommended)
cp .env.example .env        # Add your OPENROUTER_API_KEY
./deploy.sh                 # Build + start
# Open http://localhost:8000

# Manual
pip3 install -r requirements.txt
pip3 install chromadb sentence-transformers openpyxl
cd frontend && npm install && npm run build && cd ..
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Architecture

```
Phone Camera (with GPS/EXIF)
    │
    ▼
Upload → Queue (auto-process in background)
    │
    ▼
Classifier Agent → "product_page" / "contact_page" / "tech_diagram" / ...
    │
    ▼
Specialized Agent → Structured JSON
    │
    ▼
Normalize → documents + products + contacts tables (with UUIDs)
    │
    ▼
Index → SQLite FTS5 + ChromaDB vectors
    │
    ▼
Chat Agent ← RAG context + SQL tools + memory + feedback
    │
    ▼
Streaming Answer + Image Citations + Follow-up Suggestions
```

## Agent Capabilities

The chat agent is more than a simple RAG — it has **SQL tools** and **memory**:

```
User: "Who did I meet at the trade show?"
Agent: [TOOL: query_catalog_db] SELECT company, person, phone, email FROM contacts
→ Returns full contact table with Shirley (+86-15268367084), Dahua Technology, etc.

User: "How many data strip products?"
Agent: [TOOL: query_catalog_db] SELECT COUNT(*) FROM products WHERE category = 'data strips'
→ "There are 24 data strip products"

User: "Where was this catalog photographed?"
Agent: [TOOL: query_catalog_db] SELECT folder, gps_lat, gps_lng FROM documents WHERE gps_lat IS NOT NULL
→ Shows GPS coordinates from phone camera EXIF data
```

| Capability | How |
|-----------|-----|
| Count & aggregate | SQL: `SELECT COUNT(*), category FROM products GROUP BY category` |
| Filter & compare | SQL: `SELECT * FROM products WHERE company = 'Ahua'` |
| Find contacts | SQL: `SELECT company, person, phone, email FROM contacts` |
| Search products | RAG: semantic + keyword search across all catalogs |
| Remember facts | Memory: saves/recalls facts across sessions |
| Learn from feedback | Thumbs up/down improves future responses |
| Cite sources | Image citations with clickable thumbnails |
| Know locations | EXIF: GPS coordinates from phone photos |

## Database Schema

```
documents (36 rows)              products (131 rows)              contacts (6 rows)
├── uuid                         ├── uuid                         ├── uuid
├── folder                       ├── document_uuid ──FK──►        ├── document_uuid ──FK──►
├── source_file                  ├── company                      ├── company
├── image_type                   ├── name                         ├── person
├── company                      ├── model                        ├── phone
├── title                        ├── specs                        ├── email
├── gps_lat / gps_lng            ├── category                     ├── website
├── date_taken                   ├── price                        ├── address
├── camera_make / camera_model   ├── image_desc                   └── created_at
├── img_width / img_height       └── created_at
├── file_size_kb
└── created_at
```

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

## UI Features

**Chat Agent**
- Streaming SSE with RAG ANALYZING animation
- CLI execution bar with tool steps + checkmarks
- Image citations (clickable thumbnails with lightbox)
- Thumbs up/down feedback (connected to memory)
- Voice input (Web Speech API)
- Export conversation as markdown
- Session history with search
- Follow-up suggestion chips
- 60s stream timeout protection

**Data Browser**
- Filter by folder + image type, sort by date/type/company
- Expandable cards with thumbnail, products, contacts, metadata
- Metadata tags: dimensions, file size, UUID, GPS, camera, date taken
- Copy/Save JSON per document

**Queue Manager**
- Inline expand with document thumbnails
- Retry/delete failed items, toast notifications
- Processing progress with terminal log

**More Page**
- Products table (131 rows, searchable, XLSX export)
- Contacts table (6 rows, searchable)
- Companies table (14 with doc/product counts)
- Categories breakdown (28 categories)
- Product specs table (85 with specs)
- Image gallery (36 thumbnails)
- Documents table (UUID, dimensions, file size, GPS, dates)

**Upload**
- Camera + drag-drop + PDF upload (auto-splits pages)
- Real upload progress bar
- Image quality warnings
- HEIC/HEIF/AVIF/TIFF/JFIF support

## API Endpoints (25+)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/upload` | Upload images/PDFs (auto-processes) |
| `POST /api/chat/stream` | Streaming chat with SQL tools (SSE) |
| `POST /api/chat` | Non-streaming chat |
| `GET /api/products` | All products (normalized table) |
| `GET /api/contacts` | All contacts (normalized table) |
| `GET /api/dashboard` | Stats + breakdowns |
| `GET /api/documents/metadata` | Documents with EXIF metadata |
| `GET /api/search?q=` | Full-text search |
| `GET /api/search/semantic?q=` | Semantic vector search |
| `GET /api/data` | All extracted documents |
| `GET /api/queue/batches` | Queue management |
| `POST /api/queue/retry/{id}` | Retry failed extraction |
| `DELETE /api/batch/{id}` | Delete batch |
| `GET /api/export/xlsx` | Excel export (3 sheets) |
| `GET /api/export/json` | JSON export |
| `GET /api/export/csv` | CSV export |
| `POST /api/feedback` | Save thumbs up/down |
| `GET /api/memories` | Agent memories |
| `POST /api/migrate` | Run table normalization |
| `GET /api/image/{folder}/{file}` | Serve catalog images |
| `GET /api/config` | Model configuration |
| `GET /health` | Health check (Docker) |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Python 3.12 (2,467 lines) |
| Frontend | SvelteKit 5 + Tailwind v4 (4,649 lines) |
| LLM | Gemini 3.1 Flash Lite via OpenRouter |
| Embeddings | OpenAI text-embedding-3-small via OpenRouter |
| Database | SQLite (WAL) + FTS5 + normalized tables |
| Vectors | ChromaDB (persistent, local) |
| Design | Brutalist (Space Grotesk, no border-radius) |
| Deploy | Docker (multi-stage, healthcheck) |
| PWA | Installable, network-first caching |

## Environment

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
├── main.py              # FastAPI (25+ endpoints, SSE streaming)
├── chat.py              # Agent with RAG + SQL tool loop + memory
├── tools.py             # SQL tool, schema introspect, catalog summary
├── memory.py            # Feedback + memories (JSON file-based)
├── database.py          # SQLite + FTS5 + normalized tables + UUIDs
├── vectorstore.py       # ChromaDB + OpenRouter embeddings
├── config.py            # Environment-based configuration
├── pipeline/
│   ├── loader.py        # Image + PDF + EXIF extraction
│   ├── extractor.py     # Async batch extraction
│   └── agents.py        # 8 specialized extraction prompts
├── frontend/src/routes/
│   ├── upload/          # Camera/PDF upload with quality warnings
│   ├── queue/           # Batch management + inline expand
│   ├── chat/            # Agent (streaming, SQL tools, citations)
│   ├── data/            # Document browser (metadata, filter, sort)
│   └── more/            # Tables, gallery, search, export, stats
├── data/
│   ├── uploads/         # Uploaded images (portable)
│   ├── extractions/     # JSON extraction results
│   ├── chroma/          # Vector store
│   └── kontact.db       # SQLite (documents + products + contacts)
├── Dockerfile           # Multi-stage (Node + Python + healthcheck)
├── docker-compose.yml   # Production-ready
├── deploy.sh            # One-command deployment
└── .env.example         # Configuration template
```

## License

MIT

## Built by RLAI Team
