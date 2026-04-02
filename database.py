import re
import sqlite3
from datetime import date, datetime, timezone, timedelta

DB_PATH = "contests.db"
KST_OFFSET = timedelta(hours=9)


def _now_kst() -> str:
    """현재 한국 시간(KST) 문자열 반환"""
    return (datetime.now(timezone.utc) + KST_OFFSET).strftime("%Y-%m-%d %H:%M:%S")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                category TEXT,
                deadline TEXT,
                host TEXT,
                prize TEXT,
                thumbnail TEXT,
                scraped_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TEXT NOT NULL,
                total INTEGER DEFAULT 0,
                added INTEGER DEFAULT 0,
                status TEXT
            )
        """)
        conn.commit()


def upsert_contests(contests: list[dict]) -> int:
    """Insert new contests, skip duplicates. Returns count of newly added."""
    added = 0
    now = _now_kst()
    with get_conn() as conn:
        for c in contests:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO contests
                       (title, url, source, category, deadline, host, prize, thumbnail, scraped_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (c.get("title"), c.get("url"), c.get("source"),
                     c.get("category"), c.get("deadline"), c.get("host"),
                     c.get("prize"), c.get("thumbnail"), now)
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    added += 1
            except Exception as e:
                print(f"[DB] insert error: {e}")
        conn.commit()
    return added


def log_scrape(total: int, added: int, status: str):
    now = _now_kst()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO scrape_log (run_at, total, added, status) VALUES (?, ?, ?, ?)",
            (now, total, added, status)
        )
        conn.commit()


def get_contests(page: int = 1, per_page: int = 20,
                 source: str = None, keyword: str = None,
                 category: str = None) -> dict:
    offset = (page - 1) * per_page
    where, params = [], []

    if source:
        where.append("source = ?")
        params.append(source)
    if keyword:
        where.append("(title LIKE ? OR host LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if category:
        where.append("category LIKE ?")
        params.append(f"%{category}%")

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM contests {where_clause}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT * FROM contests {where_clause}
                ORDER BY scraped_at DESC, id DESC
                LIMIT ? OFFSET ?""",
            params + [per_page, offset]
        ).fetchall()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "items": [dict(r) for r in rows],
    }


def cleanup_expired() -> int:
    """마감일이 지난 공모전을 DB에서 삭제. 삭제된 건수 반환."""
    today = (datetime.now(timezone.utc) + KST_OFFSET).date()

    def _parse(text: str):
        if not text:
            return None
        clean = re.sub(r"[가-힣\s접수모집]", "", text)
        m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", clean)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        m = re.search(r"(\d{1,2})[.\-/](\d{2})$", clean)
        if m:
            try:
                return date(today.year, int(m.group(1)), int(m.group(2)))
            except ValueError:
                pass
        return None

    with get_conn() as conn:
        rows = conn.execute("SELECT id, deadline FROM contests").fetchall()
        expired_ids = [row["id"] for row in rows
                       if (d := _parse(row["deadline"])) is not None and d < today]
        if expired_ids:
            conn.execute(
                f"DELETE FROM contests WHERE id IN ({','.join('?' * len(expired_ids))})",
                expired_ids
            )
            conn.commit()

    return len(expired_ids)


def get_sources() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT source FROM contests ORDER BY source"
        ).fetchall()
    return [r["source"] for r in rows]


def get_last_scrape() -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM scrape_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None
