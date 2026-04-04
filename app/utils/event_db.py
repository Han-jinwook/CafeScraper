from __future__ import annotations

import hashlib
import re
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
            comment_grade_code TEXT,
            comment_nickname TEXT,
            comment_date TEXT,
            comment_content TEXT,
            comment_length INTEGER,
            emoji_count INTEGER DEFAULT 0,
            inline_image_count INTEGER DEFAULT 0,
            text_char_count INTEGER DEFAULT 0,
            content_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(post_id, comment_writer_id, comment_date, content_hash)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS event_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT UNIQUE,
            post_url TEXT,
            post_title TEXT,
            post_date TEXT,
            board_name TEXT,
            comments_seen INTEGER DEFAULT 0,
            comments_saved INTEGER DEFAULT 0,
            comments_excluded INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS event_post_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT UNIQUE,
            post_url TEXT,
            post_title TEXT,
            post_date TEXT,
            board_name TEXT,
            author_nickname TEXT,
            post_char_count INTEGER DEFAULT 0,
            post_image_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        if "comment_grade_code" not in cols:
            cur.execute("ALTER TABLE event_comments ADD COLUMN comment_grade_code TEXT")
        if "comment_length" not in cols:
            cur.execute("ALTER TABLE event_comments ADD COLUMN comment_length INTEGER")
            cur.execute("UPDATE event_comments SET comment_length = LENGTH(comment_content) WHERE comment_length IS NULL")
        if "emoji_count" not in cols:
            cur.execute("ALTER TABLE event_comments ADD COLUMN emoji_count INTEGER DEFAULT 0")
            cur.execute("UPDATE event_comments SET emoji_count = 0 WHERE emoji_count IS NULL")
        if "inline_image_count" not in cols:
            cur.execute("ALTER TABLE event_comments ADD COLUMN inline_image_count INTEGER DEFAULT 0")
            cur.execute("UPDATE event_comments SET inline_image_count = 0 WHERE inline_image_count IS NULL")
        if "text_char_count" not in cols:
            cur.execute("ALTER TABLE event_comments ADD COLUMN text_char_count INTEGER DEFAULT 0")
            cur.execute(
                "UPDATE event_comments SET text_char_count = COALESCE(comment_length, LENGTH(comment_content)) "
                "WHERE text_char_count IS NULL OR text_char_count = 0"
            )
    except Exception:
        pass

    # 기존 DB 백필: 댓글 테이블만 있던 데이터에서 게시글 테이블 생성
    try:
        cur.execute(
            """
            INSERT OR IGNORE INTO event_posts (
                post_id, post_url, post_title, post_date, board_name,
                comments_seen, comments_saved, comments_excluded
            )
            SELECT
                COALESCE(post_id, ''),
                COALESCE(MAX(post_url), ''),
                COALESCE(MAX(post_title), ''),
                COALESCE(MAX(post_date), ''),
                COALESCE(MAX(board_name), ''),
                COUNT(*),
                COUNT(*),
                0
            FROM event_comments
            WHERE COALESCE(post_id, '') <> ''
            GROUP BY post_id
            """
        )
    except Exception:
        pass

    # 구버전 DB 호환(event_posts/event_post_analysis 컬럼 추가)
    try:
        cur.execute("PRAGMA table_info(event_posts)")
        post_cols = [row[1] for row in cur.fetchall()]
        if "author_nickname" not in post_cols:
            cur.execute("ALTER TABLE event_posts ADD COLUMN author_nickname TEXT DEFAULT ''")
        if "post_char_count" not in post_cols:
            cur.execute("ALTER TABLE event_posts ADD COLUMN post_char_count INTEGER DEFAULT 0")
        if "post_image_count" not in post_cols:
            cur.execute("ALTER TABLE event_posts ADD COLUMN post_image_count INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cur.execute("PRAGMA table_info(event_post_analysis)")
        ana_cols = [row[1] for row in cur.fetchall()]
        if "author_nickname" not in ana_cols:
            cur.execute("ALTER TABLE event_post_analysis ADD COLUMN author_nickname TEXT DEFAULT ''")
        if "post_char_count" not in ana_cols:
            cur.execute("ALTER TABLE event_post_analysis ADD COLUMN post_char_count INTEGER DEFAULT 0")
        if "post_image_count" not in ana_cols:
            cur.execute("ALTER TABLE event_post_analysis ADD COLUMN post_image_count INTEGER DEFAULT 0")
    except Exception:
        pass
    conn.commit()
    conn.close()


def _hash_content(s: str) -> str:
    s = (s or "").strip().encode("utf-8", errors="ignore")
    return hashlib.sha1(s).hexdigest()[:16]


_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


def _count_emoji(text: str) -> int:
    if not text:
        return 0
    return sum(len(m.group(0)) for m in _EMOJI_RE.finditer(text))


def _text_char_count_without_emoji(text: str) -> int:
    if not text:
        return 0
    no_emoji = _EMOJI_RE.sub("", text)
    no_ws = re.sub(r"\s+", "", no_emoji)
    return len(no_ws)


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
        comment_id = str(c.get("comment_id") or "").strip()
        raw_writer_id = str(c.get("writer_id") or "unknown").strip()
        nickname = str(c.get("nickname") or "unknown").strip()
        # writer_id가 unknown일 때 동일 유저 구분력을 높이기 위해 닉네임 기반 키 사용
        writer_key = raw_writer_id
        if (not writer_key) or (writer_key.lower() == "unknown"):
            writer_key = f"nick::{nickname.lower()}"

        # 기존 UNIQUE(post_id, comment_writer_id, comment_date, content_hash) 제약 하에서
        # comment_id가 있으면 해시에 포함해 동일 문구 다중 댓글 누락을 줄인다.
        # 단, 기존 데이터(content만 해시)와의 호환을 위해 old/new 해시를 모두 조회해 중복 삽입을 막는다.
        old_hash = _hash_content(content)
        hash_src = content if not comment_id else f"{content}|cid:{comment_id}"
        h = _hash_content(hash_src)
        clen = len(content)
        emoji_count = int(_count_emoji(content))
        inline_image_count = int(c.get("inline_image_count") or 0)
        text_char_count = int(_text_char_count_without_emoji(content))

        comment_date = str(c.get("date") or "")
        post_id = str(post.get("post_id") or "")
        legacy_writer_key = raw_writer_id if raw_writer_id else "unknown"
        cur.execute(
            """
            SELECT 1
            FROM event_comments
            WHERE post_id = ?
              AND comment_writer_id IN (?, ?)
              AND comment_date = ?
              AND content_hash IN (?, ?)
            LIMIT 1
            """,
            (
                post_id,
                writer_key,
                legacy_writer_key,
                comment_date,
                old_hash,
                h,
            ),
        )
        if cur.fetchone() is not None:
            continue

        cur.execute(
            """
            INSERT OR IGNORE INTO event_comments (
                post_id, post_url, post_title, post_date, board_name,
                comment_id, comment_writer_id, comment_level, comment_grade_code, comment_nickname, comment_date, comment_content,
                comment_length, emoji_count, inline_image_count, text_char_count, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post_id,
                str(post.get("url") or ""),
                str(post.get("title") or ""),
                str(post.get("date") or ""),
                str(post.get("board_name") or ""),
                comment_id,
                writer_key,
                str(c.get("level") or ""),
                str(c.get("level_code") or ""),
                nickname,
                comment_date,
                content,
                int(clen),
                emoji_count,
                inline_image_count,
                text_char_count,
                h,
            ),
        )
        inserted += int(cur.rowcount == 1)

    conn.commit()
    conn.close()
    return inserted


def save_event_post(
    db_path: str,
    post: Dict[str, Any],
    *,
    comments_seen: int = 0,
    comments_saved: int = 0,
    comments_excluded: int = 0,
    author_nickname: str = "",
    post_char_count: int = 0,
    post_image_count: int = 0,
) -> None:
    """
    게시글 메타를 이벤트 DB에 저장/업데이트.
    - 댓글이 0개여도 게시글은 반드시 남긴다.
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO event_posts (
            post_id, post_url, post_title, post_date, board_name,
            comments_seen, comments_saved, comments_excluded,
            author_nickname, post_char_count, post_image_count, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(post_id) DO UPDATE SET
            post_url=excluded.post_url,
            post_title=excluded.post_title,
            post_date=excluded.post_date,
            board_name=excluded.board_name,
            comments_seen=excluded.comments_seen,
            comments_saved=excluded.comments_saved,
            comments_excluded=excluded.comments_excluded,
            author_nickname=excluded.author_nickname,
            post_char_count=excluded.post_char_count,
            post_image_count=excluded.post_image_count,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            str(post.get("post_id") or ""),
            str(post.get("url") or ""),
            str(post.get("title") or ""),
            str(post.get("date") or ""),
            str(post.get("board_name") or ""),
            int(comments_seen or 0),
            int(comments_saved or 0),
            int(comments_excluded or 0),
            str(author_nickname or ""),
            int(post_char_count or 0),
            int(post_image_count or 0),
        ),
    )
    conn.commit()
    conn.close()


def save_event_post_analysis(
    db_path: str,
    post: Dict[str, Any],
    *,
    author_nickname: str = "",
    post_char_count: int = 0,
    post_image_count: int = 0,
) -> None:
    """조건2(게시글 수집·분석) 결과 저장/업데이트."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO event_post_analysis (
            post_id, post_url, post_title, post_date, board_name,
            author_nickname, post_char_count, post_image_count, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(post_id) DO UPDATE SET
            post_url=excluded.post_url,
            post_title=excluded.post_title,
            post_date=excluded.post_date,
            board_name=excluded.board_name,
            author_nickname=excluded.author_nickname,
            post_char_count=excluded.post_char_count,
            post_image_count=excluded.post_image_count,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            str(post.get("post_id") or ""),
            str(post.get("url") or ""),
            str(post.get("title") or ""),
            str(post.get("date") or ""),
            str(post.get("board_name") or ""),
            str(author_nickname or ""),
            int(post_char_count or 0),
            int(post_image_count or 0),
        ),
    )
    conn.commit()
    conn.close()


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


def get_event_posts_count(db_path: str) -> int:
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM event_posts")
        n = cur.fetchone()[0] or 0
        conn.close()
        return int(n)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 0

