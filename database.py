import sqlite3, json, os
import config

DB_PATH = os.path.join(config.DATA_DIR, "kontact.db")


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def init_db():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_path TEXT,
            image_type TEXT,
            company TEXT,
            title TEXT,
            products TEXT,
            contact TEXT,
            key_info TEXT,
            raw_text TEXT,
            full_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(folder, source_file)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            folder, source_file, company, title, raw_text, key_info,
            content='documents',
            content_rowid='id'
        );
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, folder, source_file, company, title, raw_text, key_info)
            VALUES (new.id, new.folder, new.source_file, new.company, new.title, new.raw_text, new.key_info);
        END;
        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, folder, source_file, company, title, raw_text, key_info)
            VALUES ('delete', old.id, old.folder, old.source_file, old.company, old.title, old.raw_text, old.key_info);
        END;
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            image_type TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP
        );
    """)
    c.close()


def insert_extraction(folder: str, record: dict):
    c = _conn()
    c.execute("""
        INSERT OR REPLACE INTO documents
        (folder, source_file, source_path, image_type, company, title, products, contact, key_info, raw_text, full_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        folder,
        record.get("source_file", ""),
        record.get("source_path", ""),
        record.get("image_type", ""),
        record.get("company", ""),
        record.get("title", ""),
        json.dumps(record.get("products", []), ensure_ascii=False),
        json.dumps(record.get("contact", {}), ensure_ascii=False),
        json.dumps(record.get("key_info", []), ensure_ascii=False),
        record.get("raw_text", ""),
        json.dumps(record, ensure_ascii=False),
    ))
    c.commit()
    c.close()


def load_all_extractions():
    """Load from JSON files into SQLite."""
    ext_dir = config.EXTRACTIONS_DIR
    count = 0
    for fname in os.listdir(ext_dir):
        if fname == "all_extractions.json" or not fname.endswith(".json"):
            continue
        folder = fname.replace(".json", "")
        with open(os.path.join(ext_dir, fname)) as f:
            records = json.load(f)
        for r in records:
            insert_extraction(folder, r)
            count += 1
    return count


def search(query: str, limit: int = 20) -> list:
    import re
    # Sanitize for FTS5: keep only alphanumeric and spaces, join words with OR
    words = re.findall(r'[a-zA-Z0-9]+', query)
    if not words:
        return []
    fts_query = " OR ".join(words)
    c = _conn()
    try:
        rows = c.execute("""
            SELECT d.* FROM documents_fts f
            JOIN documents d ON d.id = f.rowid
            WHERE documents_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (fts_query, limit)).fetchall()
    except Exception:
        rows = []
    c.close()
    return [dict(r) for r in rows]


def get_all(limit: int = 500) -> list:
    c = _conn()
    rows = c.execute("SELECT * FROM documents ORDER BY folder, source_file LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_by_folder(folder: str) -> list:
    c = _conn()
    rows = c.execute("SELECT * FROM documents WHERE folder = ? ORDER BY source_file", (folder,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    folders = c.execute("SELECT DISTINCT folder FROM documents").fetchall()
    companies = c.execute("SELECT DISTINCT company FROM documents WHERE company IS NOT NULL AND company != ''").fetchall()
    c.close()
    return {
        "total_documents": total,
        "folders": [r[0] for r in folders],
        "companies": [r[0] for r in companies],
    }


def save_chat(session_id: str, role: str, content: str):
    c = _conn()
    c.execute("INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
              (session_id, role, content))
    c.commit()
    c.close()


def get_chat_history(session_id: str, limit: int = 50) -> list:
    c = _conn()
    rows = c.execute(
        "SELECT role, content, created_at FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
        (session_id, limit)).fetchall()
    c.close()
    return [dict(r) for r in reversed(rows)]


def list_sessions() -> list:
    c = _conn()
    rows = c.execute("""
        SELECT session_id, MIN(created_at) as started, MAX(created_at) as last_msg,
               COUNT(*) as messages,
               (SELECT SUBSTR(content, 1, 50) FROM chat_history ch2
                WHERE ch2.session_id = chat_history.session_id AND ch2.role = 'user'
                ORDER BY ch2.id ASC LIMIT 1) as preview
        FROM chat_history GROUP BY session_id ORDER BY last_msg DESC
    """).fetchall()
    c.close()
    return [dict(r) for r in rows]


def delete_session(session_id: str):
    c = _conn()
    c.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    c.commit()
    c.close()


def queue_add(batch_id: str, file_name: str, file_path: str):
    c = _conn()
    c.execute("INSERT INTO queue (batch_id, file_name, file_path) VALUES (?, ?, ?)",
              (batch_id, file_name, file_path))
    c.commit()
    c.close()


def queue_pending(batch_id: str = None) -> list:
    c = _conn()
    if batch_id:
        rows = c.execute("SELECT * FROM queue WHERE batch_id = ? AND status = 'pending' ORDER BY id", (batch_id,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM queue WHERE status = 'pending' ORDER BY id").fetchall()
    c.close()
    return [dict(r) for r in rows]


def queue_update(queue_id: int, status: str, image_type: str = None, error: str = None):
    c = _conn()
    c.execute("UPDATE queue SET status = ?, image_type = ?, error = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?",
              (status, image_type, error, queue_id))
    c.commit()
    c.close()


def queue_errors(batch_id: str = None) -> list:
    c = _conn()
    if batch_id:
        rows = c.execute("SELECT * FROM queue WHERE batch_id = ? AND status = 'error' ORDER BY id", (batch_id,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM queue WHERE status = 'error' ORDER BY id").fetchall()
    c.close()
    return [dict(r) for r in rows]


def queue_retry(queue_id: int):
    c = _conn()
    c.execute("UPDATE queue SET status = 'pending', error = NULL, processed_at = NULL WHERE id = ? AND status = 'error'",
              (queue_id,))
    c.commit()
    changed = c.total_changes
    c.close()
    return changed > 0


def queue_status(batch_id: str = None) -> dict:
    c = _conn()
    if batch_id:
        rows = c.execute("SELECT status, COUNT(*) as cnt FROM queue WHERE batch_id = ? GROUP BY status", (batch_id,)).fetchall()
        total = c.execute("SELECT COUNT(*) FROM queue WHERE batch_id = ?", (batch_id,)).fetchone()[0]
    else:
        rows = c.execute("SELECT status, COUNT(*) as cnt FROM queue GROUP BY status").fetchall()
        total = c.execute("SELECT COUNT(*) FROM queue").fetchone()[0]
    c.close()
    breakdown = {r["status"]: r["cnt"] for r in rows}
    return {"total": total, **breakdown}


def queue_batches() -> list:
    c = _conn()
    rows = c.execute("""
        SELECT batch_id, COUNT(*) as total,
               SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
               SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
               SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as errors,
               MIN(created_at) as created, MAX(processed_at) as last_processed
        FROM queue GROUP BY batch_id ORDER BY created DESC
    """).fetchall()
    c.close()
    return [dict(r) for r in rows]


def export_all() -> list:
    c = _conn()
    rows = c.execute("SELECT * FROM documents ORDER BY folder, source_file").fetchall()
    c.close()
    results = []
    for r in rows:
        d = dict(r)
        for field in ("products", "contact", "key_info"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        results.append(d)
    return results


init_db()
