import sqlite3, json, os
from uuid import uuid4
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
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            document_uuid TEXT,
            document_id INTEGER,
            folder TEXT,
            source_file TEXT,
            company TEXT,
            name TEXT,
            model TEXT,
            specs TEXT,
            category TEXT,
            price TEXT,
            image_desc TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            document_uuid TEXT,
            document_id INTEGER,
            folder TEXT,
            source_file TEXT,
            company TEXT,
            person TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );
    """)

    # Add uuid column to documents if not exists (SQLite has no IF NOT EXISTS for ALTER)
    try:
        c.execute("ALTER TABLE documents ADD COLUMN uuid TEXT")
        c.commit()
    except Exception:
        pass  # Column already exists

    # Add metadata column to documents if not exists
    try:
        c.execute("ALTER TABLE documents ADD COLUMN metadata TEXT")
        c.commit()
    except Exception:
        pass  # Column already exists

    # Add flat metadata columns for SQL queryability
    for col_def in [
        "gps_lat REAL",
        "gps_lng REAL",
        "date_taken TEXT",
        "camera_make TEXT",
        "camera_model TEXT",
        "img_width INTEGER",
        "img_height INTEGER",
        "file_size_kb REAL",
    ]:
        try:
            c.execute(f"ALTER TABLE documents ADD COLUMN {col_def}")
            c.commit()
        except Exception:
            pass  # Column already exists

    c.close()


def insert_extraction(folder: str, record: dict):
    c = _conn()
    doc_uuid = str(uuid4())
    metadata_json = None
    if record.get("metadata"):
        metadata_json = json.dumps(record["metadata"], ensure_ascii=False)
    # Extract flat metadata fields
    meta = record.get("metadata", {}) or {}
    gps_lat = meta.get("gps_lat")
    gps_lng = meta.get("gps_lng")
    date_taken = meta.get("date_taken")
    camera_make = meta.get("camera_make")
    camera_model = meta.get("camera_model")
    img_width = meta.get("img_width")
    img_height = meta.get("img_height")
    file_size_kb = meta.get("file_size_kb")

    c.execute("""
        INSERT OR REPLACE INTO documents
        (folder, source_file, source_path, image_type, company, title, products, contact, key_info, raw_text, full_json, uuid, metadata,
         gps_lat, gps_lng, date_taken, camera_make, camera_model, img_width, img_height, file_size_kb)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        doc_uuid,
        metadata_json,
        gps_lat, gps_lng, date_taken, camera_make, camera_model, img_width, img_height, file_size_kb,
    ))
    doc_id = c.execute("SELECT id FROM documents WHERE folder = ? AND source_file = ?",
                       (folder, record.get("source_file", ""))).fetchone()
    doc_id = doc_id[0] if doc_id else None
    source_file = record.get("source_file", "")
    company = record.get("company", "")

    # Insert products into normalized table
    products = record.get("products", [])
    if isinstance(products, str):
        try:
            products = json.loads(products)
        except Exception:
            products = []
    if isinstance(products, list):
        for p in products:
            if not isinstance(p, dict):
                continue
            p_name = p.get("product_name", "") or p.get("name", "")
            specs_val = p.get("specs", "")
            if not isinstance(specs_val, str):
                specs_val = json.dumps(specs_val, ensure_ascii=False)
            try:
                c.execute("""
                    INSERT INTO products (uuid, document_uuid, document_id, folder, source_file, company, name, model, specs, category, price, image_desc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid4()), doc_uuid, doc_id, folder, source_file,
                    p.get("company", "") or company,
                    p_name, p.get("model", ""), specs_val,
                    p.get("category", ""), p.get("price", ""),
                    p.get("image_desc", "") or p.get("description", ""),
                ))
            except Exception:
                pass  # Skip duplicates

    # Insert contact into normalized table
    contact = record.get("contact", {})
    if isinstance(contact, str):
        try:
            contact = json.loads(contact)
        except Exception:
            contact = {}
    if isinstance(contact, dict):
        ct_company = contact.get("company", "") or ""
        ct_person = contact.get("person", "") or ""
        ct_phone = contact.get("phone", "") or ""
        ct_email = contact.get("email", "") or ""
        ct_website = contact.get("website", "") or ""
        ct_address = contact.get("address", "") or ""
        if any([ct_company, ct_person, ct_phone, ct_email, ct_website, ct_address]):
            try:
                c.execute("""
                    INSERT INTO contacts (uuid, document_uuid, document_id, folder, source_file, company, person, phone, email, website, address)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid4()), doc_uuid, doc_id, folder, source_file,
                    ct_company, ct_person, ct_phone, ct_email, ct_website, ct_address,
                ))
            except Exception:
                pass

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


def delete_batch(batch_id: str) -> int:
    c = _conn()
    queue_deleted = c.execute("DELETE FROM queue WHERE batch_id = ?", (batch_id,)).rowcount
    doc_deleted = c.execute("DELETE FROM documents WHERE folder = ?", (batch_id,)).rowcount
    c.commit()
    c.close()
    return queue_deleted + doc_deleted


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


def get_all_contacts() -> list:
    """Parse contact JSON from all documents and return a flat list of contacts."""
    c = _conn()
    rows = c.execute("SELECT folder, source_file, contact FROM documents ORDER BY folder, source_file").fetchall()
    c.close()
    contacts = []
    for r in rows:
        raw = r["contact"]
        if not raw:
            continue
        try:
            ct = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if not isinstance(ct, dict):
            continue
        company = ct.get("company", "") or ""
        person = ct.get("person", "") or ""
        phone = ct.get("phone", "") or ""
        email = ct.get("email", "") or ""
        website = ct.get("website", "") or ""
        address = ct.get("address", "") or ""
        # Skip if all contact fields are empty
        if not any([company, person, phone, email, website, address]):
            continue
        contacts.append({
            "company": company,
            "person": person,
            "phone": phone,
            "email": email,
            "website": website,
            "address": address,
            "folder": r["folder"],
            "source_file": r["source_file"],
        })
    return contacts


def get_dashboard_stats() -> dict:
    """Return rich dashboard statistics."""
    c = _conn()
    total_documents = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    # Count products by parsing JSON
    rows = c.execute("SELECT folder, company, products FROM documents ORDER BY folder, company").fetchall()
    total_products = 0
    company_map = {}  # company -> {doc_count, product_count}
    for r in rows:
        company = r["company"] or "Unknown"
        if company not in company_map:
            company_map[company] = {"doc_count": 0, "product_count": 0}
        company_map[company]["doc_count"] += 1
        prods = r["products"]
        if prods:
            try:
                p = json.loads(prods) if isinstance(prods, str) else prods
                if isinstance(p, list):
                    total_products += len(p)
                    company_map[company]["product_count"] += len(p)
            except Exception:
                pass

    companies_with_counts = [
        {"company": k, "doc_count": v["doc_count"], "product_count": v["product_count"]}
        for k, v in sorted(company_map.items())
    ]

    # Type breakdown
    type_rows = c.execute(
        "SELECT image_type, COUNT(*) as cnt FROM documents GROUP BY image_type ORDER BY cnt DESC"
    ).fetchall()
    type_breakdown = [{"image_type": r["image_type"] or "unknown", "count": r["cnt"]} for r in type_rows]

    # Folder breakdown
    folder_rows = c.execute(
        "SELECT folder, COUNT(*) as cnt FROM documents GROUP BY folder ORDER BY cnt DESC"
    ).fetchall()
    folder_breakdown = [{"folder": r["folder"], "count": r["cnt"]} for r in folder_rows]

    # Recent uploads (last 5 queue items)
    recent_rows = c.execute(
        "SELECT id, batch_id, file_name, status, image_type, created_at, processed_at "
        "FROM queue ORDER BY id DESC LIMIT 5"
    ).fetchall()
    recent_uploads = [dict(r) for r in recent_rows]

    c.close()
    return {
        "total_documents": total_documents,
        "total_products": total_products,
        "companies_with_counts": companies_with_counts,
        "type_breakdown": type_breakdown,
        "folder_breakdown": folder_breakdown,
        "recent_uploads": recent_uploads,
    }


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


def populate_normalized_tables() -> dict:
    """Migrate existing documents into the normalized products and contacts tables."""
    c = _conn()
    # Only process documents that don't yet have a uuid (i.e., not yet migrated)
    rows = c.execute("SELECT * FROM documents WHERE uuid IS NULL").fetchall()
    products_added = 0
    contacts_added = 0

    for row in rows:
        doc_id = row["id"]
        folder = row["folder"]
        source_file = row["source_file"]
        company = row["company"] or ""

        # Assign uuid to document
        doc_uuid = None
        if not doc_uuid:
            doc_uuid = str(uuid4())
            c.execute("UPDATE documents SET uuid = ? WHERE id = ?", (doc_uuid, doc_id))

        # Parse and insert products
        raw_products = row["products"]
        if raw_products:
            try:
                products = json.loads(raw_products) if isinstance(raw_products, str) else raw_products
            except Exception:
                products = []
            if isinstance(products, list):
                for p in products:
                    if not isinstance(p, dict):
                        continue
                    p_name = p.get("product_name", "") or p.get("name", "")
                    specs_val = p.get("specs", "")
                    if not isinstance(specs_val, str):
                        specs_val = json.dumps(specs_val, ensure_ascii=False)
                    try:
                        c.execute("""
                            INSERT INTO products (uuid, document_uuid, document_id, folder, source_file, company, name, model, specs, category, price, image_desc)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            str(uuid4()), doc_uuid, doc_id, folder, source_file,
                            p.get("company", "") or company,
                            p_name, p.get("model", ""), specs_val,
                            p.get("category", ""), p.get("price", ""),
                            p.get("image_desc", "") or p.get("description", ""),
                        ))
                        products_added += 1
                    except Exception:
                        pass  # duplicate or other error

        # Parse and insert contacts
        raw_contact = row["contact"]
        if raw_contact:
            try:
                ct = json.loads(raw_contact) if isinstance(raw_contact, str) else raw_contact
            except Exception:
                ct = {}
            if isinstance(ct, dict):
                ct_company = ct.get("company", "") or ""
                ct_person = ct.get("person", "") or ""
                ct_phone = ct.get("phone", "") or ""
                ct_email = ct.get("email", "") or ""
                ct_website = ct.get("website", "") or ""
                ct_address = ct.get("address", "") or ""
                if any([ct_company, ct_person, ct_phone, ct_email, ct_website, ct_address]):
                    try:
                        c.execute("""
                            INSERT INTO contacts (uuid, document_uuid, document_id, folder, source_file, company, person, phone, email, website, address)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            str(uuid4()), doc_uuid, doc_id, folder, source_file,
                            ct_company, ct_person, ct_phone, ct_email, ct_website, ct_address,
                        ))
                        contacts_added += 1
                    except Exception:
                        pass

    c.commit()
    c.close()
    return {"products_added": products_added, "contacts_added": contacts_added}


def get_products_table(limit: int = 500) -> list:
    """SELECT from the normalized products table."""
    c = _conn()
    rows = c.execute("SELECT * FROM products ORDER BY company, name LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_contacts_table(limit: int = 500) -> list:
    """SELECT from the normalized contacts table."""
    c = _conn()
    rows = c.execute("SELECT * FROM contacts ORDER BY company, person LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_documents_with_metadata(limit: int = 500) -> list:
    """Return documents with parsed metadata."""
    c = _conn()
    rows = c.execute(
        "SELECT id, uuid, folder, source_file, image_type, company, metadata, created_at FROM documents ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    c.close()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except Exception:
                d["metadata"] = {}
        else:
            d["metadata"] = {}
        results.append(d)
    return results


def backfill_metadata_columns():
    """Read the metadata JSON column for all documents and populate the flat metadata columns."""
    c = _conn()
    rows = c.execute(
        "SELECT id, metadata FROM documents WHERE metadata IS NOT NULL AND gps_lat IS NULL AND camera_make IS NULL AND date_taken IS NULL"
    ).fetchall()
    for row in rows:
        try:
            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        c.execute("""
            UPDATE documents SET
                gps_lat = ?, gps_lng = ?, date_taken = ?, camera_make = ?,
                camera_model = ?, img_width = ?, img_height = ?, file_size_kb = ?
            WHERE id = ?
        """, (
            meta.get("gps_lat"), meta.get("gps_lng"), meta.get("date_taken"),
            meta.get("camera_make"), meta.get("camera_model"),
            meta.get("img_width"), meta.get("img_height"), meta.get("file_size_kb"),
            row["id"],
        ))
    c.commit()
    c.close()


init_db()
backfill_metadata_columns()
populate_normalized_tables()
