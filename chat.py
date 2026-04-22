import httpx, json, re
import config
import database as db
import vectorstore as vs
from tools import execute_tool
from memory import build_learning_context


# ── Tool-calling markers ─────────────────────────────────────────────────────

_TOOL_PATTERN = re.compile(
    r'\[TOOL:\s*(\w+)\]\s*\n?(.*?)\n?\[/TOOL\]',
    re.DOTALL,
)

MAX_TOOL_ITERATIONS = 3


def _parse_tool_calls(text: str) -> list[dict]:
    """Extract tool calls from LLM output."""
    calls = []
    for match in _TOOL_PATTERN.finditer(text):
        name = match.group(1).strip()
        raw_args = match.group(2).strip()
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {"_raw": raw_args}
        calls.append({"name": name, "args": args, "full_match": match.group(0)})
    return calls


def _has_tool_calls(text: str) -> bool:
    return bool(_TOOL_PATTERN.search(text))


# ── Context builder (backward-compatible) ────────────────────────────────────

def _build_context(question: str) -> str:
    semantic = vs.query(question, n_results=5)
    fts = db.search(question, limit=3)

    seen = set()
    chunks = []
    for r in semantic:
        doc_id = r["id"]
        if doc_id not in seen:
            seen.add(doc_id)
            chunks.append(f"[{r['metadata']['folder']}] {r['metadata'].get('company','')}\n{r['text']}")

    for r in fts:
        doc_id = f"{r['folder']}/{r['source_file']}"
        if doc_id not in seen:
            seen.add(doc_id)
            chunks.append(f"[{r['folder']}] {r.get('company','')}\n{r.get('raw_text','')}")

    return "\n---\n".join(chunks[:8])


# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_BASE = """You are KONTACT, a catalog intelligence agent. You help users explore and analyze product catalogs, brochures, and trade show materials that have been scanned and indexed.

## Capabilities

1. **Knowledge Base Search** -- RAG context with product descriptions, specs, and company info is provided with each question.
2. **SQL Tools** -- You can run queries against the catalog database for precise counting, filtering, and aggregation.

## Available Tools

You can invoke tools by outputting a JSON block in this exact format:

[TOOL: query_catalog_db]
{"sql": "SELECT company, COUNT(*) as cnt FROM documents GROUP BY company ORDER BY cnt DESC"}
[/TOOL]

[TOOL: introspect_schema]
{}
[/TOOL]

[TOOL: get_catalog_summary]
{}
[/TOOL]

### Tool descriptions:
- **query_catalog_db** -- Run a read-only SQL SELECT on the catalog database. Argument: {"sql": "..."}
  - Table `documents` has columns: id, uuid, folder, source_file, source_path, image_type, company, title, products (JSON), contact (JSON), key_info (JSON), raw_text, full_json, created_at
  - Table `products` (normalized, one row per product): id, uuid, document_uuid, document_id, folder, source_file, company, name, model, specs, category, price, image_desc, created_at
  - Table `contacts` (normalized, one row per contact): id, uuid, document_uuid, document_id, folder, source_file, company, person, phone, email, website, address, created_at
  - Table `documents_fts` is an FTS5 virtual table for full-text search
  - **Prefer querying `products` and `contacts` tables** for structured product/contact queries instead of parsing JSON from `documents`
- **introspect_schema** -- Get the full database schema. No arguments needed.
- **get_catalog_summary** -- Get a high-level overview of all companies, document types, and folders. No arguments needed.

## Guidelines

- Use **SQL tools** for counting, aggregating, filtering, and comparing (e.g. "how many products from company X?", "list all companies", "which folder has the most pages?").
- Use **RAG context** for detailed product descriptions, specs, and qualitative answers.
- Always **validate** your results -- if a count seems off, double-check.
- **Cite sources** when possible -- mention company names, product models, folder names.
- Keep answers **concise and structured**. Use bullet points or tables for lists.
- If you cannot find the answer in the context or via tools, say so honestly.
- Do NOT fabricate product specs or company details."""


def _build_system_prompt() -> str:
    """Assemble the full system prompt with learning context."""
    parts = [_SYSTEM_BASE]

    learning = build_learning_context()
    if learning:
        parts.append(f"\n\n## What You Already Know\n\n{learning}")

    return "\n".join(parts)


# Expose SYSTEM as a property for backward compat (main.py streaming reads chat.SYSTEM)
SYSTEM = _SYSTEM_BASE  # static fallback; streaming endpoint should call _build_system_prompt()


# ── LLM call helper ─────────────────────────────────────────────────────────

async def _call_llm(messages: list, max_tokens: int = 2000, temperature: float = 0.1) -> str:
    payload = {
        "model": config.VISION_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(config.OPENROUTER_BASE, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ── Tool execution loop ──────────────────────────────────────────────────────

async def _run_tool_loop(messages: list, initial_response: str) -> str:
    """
    If the LLM response contains tool calls, execute them and feed results
    back for up to MAX_TOOL_ITERATIONS rounds.
    Returns the final answer text.
    """
    response = initial_response

    for iteration in range(MAX_TOOL_ITERATIONS):
        tool_calls = _parse_tool_calls(response)
        if not tool_calls:
            break

        # Execute each tool and build a result message
        tool_results = []
        for tc in tool_calls:
            result = execute_tool(tc["name"], tc["args"])
            tool_results.append(f"[RESULT: {tc['name']}]\n{result}\n[/RESULT]")

        result_block = "\n\n".join(tool_results)

        # Append the assistant's tool-calling message and the tool results
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": f"Tool results:\n\n{result_block}\n\nNow provide your final answer based on these results. Do not call more tools unless absolutely necessary."})

        response = await _call_llm(messages)

    # Strip any leftover tool markers from the final response
    response = _TOOL_PATTERN.sub("", response).strip()
    return response


# ── Main ask function ────────────────────────────────────────────────────────

async def ask(question: str, session_id: str = None, history: list = None) -> dict:
    context = _build_context(question)
    system_prompt = _build_system_prompt()

    if session_id and not history:
        history = db.get_chat_history(session_id, limit=6)

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for h in history[-6:]:
            messages.append({"role": h["role"], "content": h["content"]})

    messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"})

    # First LLM call
    response = await _call_llm(messages)

    # Tool execution loop (if the LLM wants to use tools)
    if _has_tool_calls(response):
        response = await _run_tool_loop(messages, response)

    sources = []
    for s in vs.query(question, n_results=3):
        sources.append({"folder": s["metadata"]["folder"], "file": s["metadata"]["source_file"],
                        "company": s["metadata"].get("company", "")})

    if session_id:
        db.save_chat(session_id, "user", question)
        db.save_chat(session_id, "assistant", response)

    return {"answer": response, "sources": sources, "session_id": session_id}
