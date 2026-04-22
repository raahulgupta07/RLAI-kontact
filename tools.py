"""
SQL tool system for KONTACT — gives the chat agent structured access
to the catalog database via read-only SQL, schema introspection, and
a pre-built summary.
"""

import sqlite3
import json
import os
import config

DB_PATH = os.path.join(config.DATA_DIR, "kontact.db")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def _rows_to_markdown(rows: list, columns: list[str]) -> str:
    """Convert a list of sqlite3.Row objects into a markdown table string."""
    if not rows:
        return "_No results._"

    # Header
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]

    for row in rows:
        cells = []
        for col in columns:
            val = row[col]
            if val is None:
                cells.append("")
            else:
                # Truncate long values so the table stays readable
                s = str(val)
                if len(s) > 120:
                    s = s[:117] + "..."
                # Escape pipes inside cell values
                s = s.replace("|", "\\|").replace("\n", " ")
                cells.append(s)
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 1 — query_catalog_db
# ---------------------------------------------------------------------------

_BLOCKED_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
                     "REPLACE", "ATTACH", "DETACH", "VACUUM", "REINDEX",
                     "PRAGMA"}


def query_catalog_db(sql: str) -> str:
    """
    Execute a read-only SQL query against kontact.db and return the results
    as a markdown table.  Max 50 rows.  Only SELECT / WITH statements are
    permitted.
    """
    sql = sql.strip().rstrip(";")

    # Basic write-protection
    first_word = sql.split()[0].upper() if sql.split() else ""
    if first_word not in ("SELECT", "WITH", "EXPLAIN"):
        return "Error: Only SELECT / WITH queries are allowed."

    upper_sql = sql.upper()
    for kw in _BLOCKED_KEYWORDS:
        # Check for the keyword as a whole word
        if f" {kw} " in f" {upper_sql} " or upper_sql.startswith(kw):
            return f"Error: `{kw}` statements are not allowed (read-only mode)."

    # Enforce row limit
    if "LIMIT" not in upper_sql:
        sql += " LIMIT 50"

    conn = _conn()
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        if not rows:
            return "_Query returned no rows._"
        columns = [desc[0] for desc in cursor.description]
        return _rows_to_markdown(rows, columns)
    except Exception as e:
        return f"SQL error: {e}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 2 — introspect_schema
# ---------------------------------------------------------------------------

def introspect_schema(table_name: str = None) -> str:
    """
    If table_name is None, list every table in the database.
    If table_name is given, show columns with types, the row count,
    and 3 sample rows.
    """
    conn = _conn()
    try:
        if table_name is None:
            rows = conn.execute(
                "SELECT name, type FROM sqlite_master "
                "WHERE type IN ('table', 'view') ORDER BY name"
            ).fetchall()
            if not rows:
                return "_No tables found._"
            lines = ["| Table | Type |", "| --- | --- |"]
            for r in rows:
                lines.append(f"| {r['name']} | {r['type']} |")
            return "\n".join(lines)

        # --- specific table ---
        cols = conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()
        if not cols:
            return f"Error: Table `{table_name}` not found."

        lines = [f"### Table: `{table_name}`\n"]
        lines.append("| # | Column | Type | Nullable | Default | PK |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for c in cols:
            nullable = "YES" if c["notnull"] == 0 else "NO"
            default = c["dflt_value"] if c["dflt_value"] is not None else ""
            pk = "YES" if c["pk"] else ""
            lines.append(
                f"| {c['cid']} | {c['name']} | {c['type']} "
                f"| {nullable} | {default} | {pk} |"
            )

        # Row count
        try:
            count = conn.execute(
                f"SELECT COUNT(*) as cnt FROM [{table_name}]"
            ).fetchone()["cnt"]
            lines.append(f"\n**Row count:** {count:,}")
        except Exception:
            lines.append("\n**Row count:** (unable to determine)")

        # Sample rows
        try:
            sample_cursor = conn.execute(
                f"SELECT * FROM [{table_name}] LIMIT 3"
            )
            sample_rows = sample_cursor.fetchall()
            if sample_rows:
                sample_cols = [d[0] for d in sample_cursor.description]
                lines.append("\n**Sample rows (3):**\n")
                lines.append(_rows_to_markdown(sample_rows, sample_cols))
        except Exception:
            pass

        return "\n".join(lines)

    except Exception as e:
        return f"Error: {e}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool 3 — get_catalog_summary
# ---------------------------------------------------------------------------

def get_catalog_summary() -> str:
    """
    Return a bird's-eye summary of the catalog database: total documents,
    total products, companies, folders, and product categories.
    """
    conn = _conn()
    try:
        # Total documents
        total_docs = conn.execute(
            "SELECT COUNT(*) as cnt FROM documents"
        ).fetchone()["cnt"]

        # Companies
        companies = conn.execute(
            "SELECT DISTINCT company FROM documents "
            "WHERE company IS NOT NULL AND company != '' "
            "ORDER BY company"
        ).fetchall()
        company_list = [r["company"] for r in companies]

        # Folders
        folders = conn.execute(
            "SELECT folder, COUNT(*) as cnt FROM documents "
            "GROUP BY folder ORDER BY folder"
        ).fetchall()

        # Image types
        image_types = conn.execute(
            "SELECT image_type, COUNT(*) as cnt FROM documents "
            "GROUP BY image_type ORDER BY cnt DESC"
        ).fetchall()

        # Products — parse JSON and count / collect categories
        product_rows = conn.execute(
            "SELECT products FROM documents "
            "WHERE products IS NOT NULL AND products != '[]' AND products != ''"
        ).fetchall()

        total_products = 0
        categories: set = set()

        for row in product_rows:
            raw = row["products"]
            if not raw:
                continue
            try:
                items = json.loads(raw)
                if isinstance(items, list):
                    total_products += len(items)
                    for item in items:
                        cat = None
                        if isinstance(item, dict):
                            cat = (
                                item.get("category")
                                or item.get("product_category")
                                or item.get("type")
                            )
                        if cat and isinstance(cat, str) and cat.strip():
                            categories.add(cat.strip())
            except (json.JSONDecodeError, TypeError):
                pass

        # Products table count (normalized)
        try:
            products_table_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM products"
            ).fetchone()["cnt"]
        except Exception:
            products_table_count = 0

        # Contacts table count (normalized)
        try:
            contacts_table_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM contacts"
            ).fetchone()["cnt"]
        except Exception:
            contacts_table_count = 0

        # Contacts with phone numbers
        try:
            contacts_with_phone = conn.execute(
                "SELECT COUNT(*) as cnt FROM contacts WHERE phone IS NOT NULL AND phone != ''"
            ).fetchone()["cnt"]
        except Exception:
            contacts_with_phone = 0

        # Documents with GPS data
        try:
            docs_with_gps = conn.execute(
                "SELECT COUNT(*) as cnt FROM documents WHERE gps_lat IS NOT NULL"
            ).fetchone()["cnt"]
        except Exception:
            docs_with_gps = 0

        # Documents with date_taken
        try:
            docs_with_date = conn.execute(
                "SELECT COUNT(*) as cnt FROM documents WHERE date_taken IS NOT NULL AND date_taken != ''"
            ).fetchone()["cnt"]
        except Exception:
            docs_with_date = 0

        # Build the summary
        lines = [
            "## KONTACT Catalog Summary\n",
            f"- **Total documents (pages):** {total_docs:,}",
            f"- **Total products extracted:** {total_products:,}",
            f"- **Products table (normalized):** {products_table_count:,}",
            f"- **Contacts table (normalized):** {contacts_table_count:,}",
            f"- **Contacts with phone numbers:** {contacts_with_phone:,}",
            f"- **Documents with GPS data:** {docs_with_gps:,}",
            f"- **Documents with date_taken:** {docs_with_date:,}",
            f"- **Companies:** {len(company_list)}",
        ]

        if company_list:
            lines.append("  - " + ", ".join(company_list))

        lines.append(f"- **Folders:** {len(folders)}")
        for f in folders:
            lines.append(f"  - `{f['folder']}` — {f['cnt']} doc(s)")

        if image_types:
            lines.append(f"- **Image types:**")
            for it in image_types:
                t = it["image_type"] or "(unclassified)"
                lines.append(f"  - {t}: {it['cnt']}")

        if categories:
            sorted_cats = sorted(categories)
            lines.append(f"- **Product categories:** {len(sorted_cats)}")
            lines.append("  - " + ", ".join(sorted_cats))
        else:
            lines.append("- **Product categories:** _(none extracted)_")

        # Queue snapshot
        try:
            q_status = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM queue GROUP BY status"
            ).fetchall()
            if q_status:
                lines.append("\n### Processing Queue")
                for qs in q_status:
                    lines.append(f"  - {qs['status']}: {qs['cnt']}")
        except Exception:
            pass

        return "\n".join(lines)

    except Exception as e:
        return f"Error building summary: {e}"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tool dispatcher (for agent integration)
# ---------------------------------------------------------------------------

TOOLS = {
    "query_catalog_db": query_catalog_db,
    "introspect_schema": introspect_schema,
    "get_catalog_summary": get_catalog_summary,
}


def execute_tool(name: str, args: dict) -> str:
    """Dispatch a tool call by name. Returns a string result."""
    fn = TOOLS.get(name)
    if not fn:
        return f"Error: Unknown tool `{name}`."
    try:
        return fn(**args)
    except Exception as e:
        return f"Error executing {name}: {e}"
