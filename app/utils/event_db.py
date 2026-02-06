from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, Optional


def init_event_db(db_path: str) -> None:
    """
    이벤트용 댓글 수집 DB 초기화.
    - 목적: 매달 새로 초기화/교체 가능한 별도 DB로 운용
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS event_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT,
            post_url TEXT,
            post_title TEXT,
            post_date TEXT,
            board_name TEXT,
            comment_id TEXT,
            comment_writer_id TEXT,
            comment_level TEXT,
            comment_nickname TEXT,
            comment_date TEXT,
            comment_content TEXT,
            comment_length INTEGER,
            content_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(post_id, comment_writer_id, comment_date, content_hash)
        )
        """
    )

    # 구버전 DB 호환(컬럼 추가)
    try:
        cur.execute("PRAGMA table_info(event_comments)")
        cols = [row[1] for row in cur.fetchall()]
        if "comment_id" not in cols:
            cur.execute("ALTER TABLE event_comments ADD COLUMN comment_id TEXT")
        if "comment_level" not in cols:
            cur.execute("ALTER TABLE event_comments ADD COLUMN comment_level TEXT")
        if "comment_length" not in cols:
            cur.execute("ALTER TABLE event_comments ADD COLUMN comment_length INTEGER")
            cur.execute("UPDATE event_comments SET comment_length = LENGTH(comment_content) WHERE comment_length IS NULL")
    except Exception:
        pass
    conn.commit()
    conn.close()


def _hash_content(s: str) -> str:
    s = (s or "").strip().encode("utf-8", errors="ignore")
    return hashlib.sha1(s).hexdigest()[:16]


def save_event_comments(
    db_path: str,
    post: Dict[str, Any],
    comments: Iterable[Dict[str, Any]],
) -> int:
    """
    댓글 리스트를 이벤트 DB에 저장.
    - 중복은 UNIQUE + INSERT OR IGNORE로 방지
    - 반환: 실제로 신규 저장된 row 수(추정)
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()

    inserted = 0
    for c in comments:
        content = str(c.get("content") or "")
        h = _hash_content(content)
        clen = len(content)

        cur.execute(
            """
            INSERT OR IGNORE INTO event_comments (
                post_id, post_url, post_title, post_date, board_name,
                comment_id, comment_writer_id, comment_level, comment_nickname, comment_date, comment_content,
                comment_length, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(post.get("post_id") or ""),
                str(post.get("url") or ""),
                str(post.get("title") or ""),
                str(post.get("date") or ""),
                str(post.get("board_name") or ""),
                str(c.get("comment_id") or ""),
                str(c.get("writer_id") or "unknown"),
                str(c.get("level") or ""),
                str(c.get("nickname") or "unknown"),
                str(c.get("date") or ""),
                content,
                int(clen),
                h,
            ),
        )
        inserted += int(cur.rowcount == 1)

    conn.commit()
    conn.close()
    return inserted


def get_event_comments_count(db_path: str) -> int:
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM event_comments")
        n = cur.fetchone()[0] or 0
        conn.close()
        return int(n)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 0

