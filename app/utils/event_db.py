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
            post_title_char_count INTEGER DEFAULT 0,
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
            post_title_char_count INTEGER DEFAULT 0,
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
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS event_mentor_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT NOT NULL,
            member_grade TEXT NOT NULL,
            visit_count INTEGER NOT NULL DEFAULT 0,
            last_visit_date TEXT DEFAULT '',
            collect_seq INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(nickname, member_grade)
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
        if "post_title_char_count" not in post_cols:
            cur.execute("ALTER TABLE event_posts ADD COLUMN post_title_char_count INTEGER DEFAULT 0")
            cur.execute(
                "UPDATE event_posts SET post_title_char_count = LENGTH(COALESCE(post_title, '')) "
                "WHERE post_title_char_count IS NULL OR post_title_char_count = 0"
            )
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
        if "post_title_char_count" not in ana_cols:
            cur.execute("ALTER TABLE event_post_analysis ADD COLUMN post_title_char_count INTEGER DEFAULT 0")
            cur.execute(
                "UPDATE event_post_analysis SET post_title_char_count = LENGTH(COALESCE(post_title, '')) "
                "WHERE post_title_char_count IS NULL OR post_title_char_count = 0"
            )
    except Exception:
        pass

    try:
        cur.execute("PRAGMA table_info(event_mentor_visits)")
        mv_cols = [row[1] for row in cur.fetchall()]
        if "last_visit_date" not in mv_cols:
            cur.execute("ALTER TABLE event_mentor_visits ADD COLUMN last_visit_date TEXT DEFAULT ''")
        if "collect_seq" not in mv_cols:
            cur.execute("ALTER TABLE event_mentor_visits ADD COLUMN collect_seq INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

    # 자동 댓글러: 타겟 목록 스냅샷(세션 대신 재실행·새로고침 후 복원용)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS commenter_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT,
            url TEXT NOT NULL UNIQUE,
            nickname TEXT,
            title TEXT,
            date TEXT,
            board_name TEXT,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    try:
        cur.execute("PRAGMA table_info(commenter_targets)")
        _ct_cols = [row[1] for row in cur.fetchall()]
        if "comment_status" not in _ct_cols:
            cur.execute("ALTER TABLE commenter_targets ADD COLUMN comment_status TEXT")
        if "comment_detail" not in _ct_cols:
            cur.execute("ALTER TABLE commenter_targets ADD COLUMN comment_detail TEXT")
        if "comment_tried_at" not in _ct_cols:
            cur.execute("ALTER TABLE commenter_targets ADD COLUMN comment_tried_at TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()


def replace_commenter_targets(db_path: str, rows: list[dict]) -> None:
    """타겟 표 스냅샷을 DB에 덮어씀(수집 직후 호출).

    기존 구현은 `DELETE` 후 전부 다시 넣어 **2단계 재수집**만 해도 댓글 성공·실패 기록이 초기화됨.
    동일 기간을 다시 돌려도 결과를 잃지 않도록, **`comment_status`가 있는 URL**은
    새 행에 합류할 때 상태·메시지·시도 시각을 이어 받는다."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        preserved: dict[str, tuple[str, str | None, str | None]] = {}
        try:
            cur.execute(
                "SELECT url, comment_status, comment_detail, comment_tried_at FROM commenter_targets"
            )
            for ur, cs, cd, ct in cur.fetchall():
                st = str(cs or "").strip()
                if not st:
                    continue
                tup = (
                    st,
                    (str(cd).strip() if cd else None) or None,
                    (str(ct).strip() if ct else None) or None,
                )
                u0 = str(ur or "").strip()
                if not u0:
                    continue
                for key in dict.fromkeys([u0, u0.rstrip("/")]):
                    preserved[key] = tup
        except Exception:
            pass

        cur.execute("DELETE FROM commenter_targets")
        for r in rows or []:
            u = str((r or {}).get("url") or "").strip()
            if not u:
                continue

            incoming_cs = str((r or {}).get("comment_status") or "").strip()
            incoming_cd = str((r or {}).get("comment_detail") or "").strip()
            incoming_ct = str((r or {}).get("comment_tried_at") or "").strip()

            cs_out = incoming_cs or None
            cd_out = (incoming_cd or None) if incoming_cd else None
            ct_out = (incoming_ct or None) if incoming_ct else None

            if not cs_out:
                for key in dict.fromkeys([u, u.rstrip("/")]):
                    if key in preserved:
                        pcs, pcd, pct = preserved[key]
                        cs_out, cd_out, ct_out = pcs, pcd, pct
                        break

            cur.execute(
                """
                INSERT INTO commenter_targets (
                    post_id, url, nickname, title, date, board_name,
                    comment_status, comment_detail, comment_tried_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str((r or {}).get("post_id") or ""),
                    u,
                    str((r or {}).get("nickname") or ""),
                    str((r or {}).get("title") or ""),
                    str((r or {}).get("date") or ""),
                    str((r or {}).get("board_name") or ""),
                    cs_out,
                    cd_out,
                    ct_out,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def update_commenter_target_comment_status(
    db_path: str, url: str, status: str, detail: str = ""
) -> int:
    """타겟 URL 한 건에 대해 댓글 시도 결과를 저장. 반환: 변경된 행 수(0이면 URL 미일치 가능)."""
    url = str(url).strip()
    if not url:
        return 0
    status = str(status or "")[:48]
    detail = (detail or "")[:2000]
    tried_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # `/` 유무로 DB 행과 불일치할 수 있어 후보 URL을 순서대로 시도
    _cands = list(dict.fromkeys([url, url.rstrip("/")]))
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        n = 0
        for uq in _cands:
            cur.execute(
                """
                UPDATE commenter_targets
                SET comment_status = ?, comment_detail = ?, comment_tried_at = ?
                WHERE url = ?
                """,
                (status, detail, tried_at, uq),
            )
            n += int(cur.rowcount or 0)
            if n:
                break
        conn.commit()
        return n
    finally:
        conn.close()


def get_commenter_targets_count(db_path: str) -> int:
    """commenter_targets 행 수 (테이블 없음/쿼리 실패 시 0)."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM commenter_targets")
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0
    finally:
        conn.close()


def clear_commenter_targets(db_path: str) -> None:
    """자동댓글러 타겟 스냅샷 테이블만 전부 삭제 (다른 이벤트 테이블은 유지)."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM commenter_targets")
        try:
            cur.execute("DELETE FROM sqlite_sequence WHERE name = 'commenter_targets'")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def load_commenter_targets(db_path: str) -> list[dict[str, Any]]:
    """저장된 타겟 스냅샷을 행 dict 리스트로 로드."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT post_id, url, nickname, title, date, board_name,
                   comment_status, comment_detail
            FROM commenter_targets
            ORDER BY id ASC
            """
        )
        cols = (
            "post_id",
            "url",
            "nickname",
            "title",
            "date",
            "board_name",
            "comment_status",
            "comment_detail",
        )
        out: list[dict[str, Any]] = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["comment_status"] = str(d.get("comment_status") or "").strip()
            d["comment_detail"] = str(d.get("comment_detail") or "").strip()
            out.append(d)
        return out
    finally:
        conn.close()


def init_booster_db(db_path: str) -> None:
    """조회수 부스터용 DB 및 테이블 초기화."""
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
        CREATE TABLE IF NOT EXISTS booster_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT,
            url TEXT UNIQUE,
            nickname TEXT,
            title TEXT,
            date TEXT,
            board_name TEXT,
            current_view_count INTEGER DEFAULT 0,
            boosted_count INTEGER DEFAULT 0,
            last_boosted_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def replace_booster_targets(db_path: str, rows: list[dict]) -> None:
    """새로 수집된 타겟글로 스냅샷을 교체하되, 기존에 성공한 결과(boosted_count, last_boosted_at)는 보존."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        # 1. 기존 결과 백업
        cur.execute("SELECT url, boosted_count, last_boosted_at FROM booster_targets")
        history = {row[0]: (row[1], row[2]) for row in cur.fetchall() if row[0]}
        
        # 2. 기존 테이블 비우기
        cur.execute("DELETE FROM booster_targets")
        try:
            cur.execute("DELETE FROM sqlite_sequence WHERE name = 'booster_targets'")
        except Exception:
            pass
            
        # 3. 새로운 로우 삽입 (백업 데이터 결합)
        for r in rows:
            url = str(r.get("url") or "").strip()
            prev_boost = history.get(url)
            boosted_count = prev_boost[0] if prev_boost else 0
            last_boosted_at = prev_boost[1] if prev_boost else ""
            
            cur.execute(
                """
                INSERT INTO booster_targets (
                    post_id, url, nickname, title, date, board_name,
                    current_view_count, boosted_count, last_boosted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(r.get("post_id") or ""),
                    url,
                    str(r.get("nickname") or ""),
                    str(r.get("title") or ""),
                    str(r.get("date") or ""),
                    str(r.get("board_name") or ""),
                    int(r.get("current_view_count") or r.get("view_count") or 0),
                    boosted_count,
                    last_boosted_at
                )
            )
        conn.commit()
    finally:
        conn.close()


def update_booster_target_status(db_path: str, url: str, view_count: int, is_success: bool = True) -> None:
    """특정 게시글의 조회수 부스팅 성공 시 boosted_count 증가 및 정보 갱신."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if is_success:
            cur.execute(
                """
                UPDATE booster_targets
                SET current_view_count = ?,
                    boosted_count = boosted_count + 1,
                    last_boosted_at = ?
                WHERE url = ?
                """,
                (view_count, now_str, url)
            )
        else:
            cur.execute(
                """
                UPDATE booster_targets
                SET current_view_count = ?
                WHERE url = ?
                """,
                (view_count, url)
            )
        conn.commit()
    finally:
        conn.close()


def load_booster_targets(db_path: str) -> list[dict[str, Any]]:
    """저장된 타겟 글 목록을 행 dict 리스트로 로드."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT post_id, url, nickname, title, date, board_name,
                   current_view_count, boosted_count, last_boosted_at
            FROM booster_targets
            ORDER BY id ASC
            """
        )
        cols = (
            "post_id",
            "url",
            "nickname",
            "title",
            "date",
            "board_name",
            "current_view_count",
            "boosted_count",
            "last_boosted_at",
        )
        out: list[dict[str, Any]] = []
        for row in cur.fetchall():
            out.append(dict(zip(cols, row)))
        return out
    finally:
        conn.close()


def clear_booster_targets(db_path: str) -> None:
    """타겟 테이블 삭제."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM booster_targets")
        try:
            cur.execute("DELETE FROM sqlite_sequence WHERE name = 'booster_targets'")
        except Exception:
            pass
        conn.commit()
    finally:
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
            # 중복으로 삽입이 생략되는 경우에도 게시글 메타(post_date/title/url/board)는 최신값으로 동기화.
            # (목록 수집 보정 후 재실행 시 과거 post_date가 계속 남는 문제 방지)
            cur.execute(
                """
                UPDATE event_comments
                SET
                    post_url = ?,
                    post_title = ?,
                    post_date = ?,
                    board_name = ?
                WHERE post_id = ?
                  AND comment_writer_id IN (?, ?)
                  AND comment_date = ?
                  AND content_hash IN (?, ?)
                """,
                (
                    str(post.get("url") or ""),
                    str(post.get("title") or ""),
                    str(post.get("date") or ""),
                    str(post.get("board_name") or ""),
                    post_id,
                    writer_key,
                    legacy_writer_key,
                    comment_date,
                    old_hash,
                    h,
                ),
            )
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
    post_title = str(post.get("title") or "")
    post_title_char_count = len(post_title)
    cur.execute(
        """
        INSERT INTO event_posts (
            post_id, post_url, post_title, post_date, board_name,
            comments_seen, comments_saved, comments_excluded,
            author_nickname, post_char_count, post_image_count, post_title_char_count, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
            post_title_char_count=excluded.post_title_char_count,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            str(post.get("post_id") or ""),
            str(post.get("url") or ""),
            post_title,
            str(post.get("date") or ""),
            str(post.get("board_name") or ""),
            int(comments_seen or 0),
            int(comments_saved or 0),
            int(comments_excluded or 0),
            str(author_nickname or ""),
            int(post_char_count or 0),
            int(post_image_count or 0),
            int(post_title_char_count or 0),
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
    post_title = str(post.get("title") or "")
    post_title_char_count = len(post_title)
    cur.execute(
        """
        INSERT INTO event_post_analysis (
            post_id, post_url, post_title, post_date, board_name,
            author_nickname, post_char_count, post_image_count, post_title_char_count, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(post_id) DO UPDATE SET
            post_url=excluded.post_url,
            post_title=excluded.post_title,
            post_date=excluded.post_date,
            board_name=excluded.board_name,
            author_nickname=excluded.author_nickname,
            post_char_count=excluded.post_char_count,
            post_image_count=excluded.post_image_count,
            post_title_char_count=excluded.post_title_char_count,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            str(post.get("post_id") or ""),
            str(post.get("url") or ""),
            post_title,
            str(post.get("date") or ""),
            str(post.get("board_name") or ""),
            str(author_nickname or ""),
            int(post_char_count or 0),
            int(post_image_count or 0),
            int(post_title_char_count or 0),
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


def get_existing_post_ids(db_path: str) -> set:
    """DB에 이미 저장된 post_id 집합 반환 (skip 판단용)."""
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cur = conn.cursor()
        cur.execute("SELECT post_id FROM event_posts WHERE post_id IS NOT NULL AND post_id != ''")
        ids = {str(row[0]) for row in cur.fetchall()}
        conn.close()
        return ids
    except Exception:
        return set()


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


def upsert_event_mentor_visits(db_path: str, rows: Iterable[Dict[str, Any]]) -> int:
    """멘토(등급별) 방문수 스냅샷. (nickname, member_grade) 기준으로 덮어쓰기."""
    n = 0
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    try:
        for idx, r in enumerate(rows):
            nick = str((r or {}).get("nickname") or "").strip()
            grade = str((r or {}).get("member_grade") or "").strip()
            if not nick or not grade:
                continue
            try:
                vc = int((r or {}).get("visit_count") or 0)
            except Exception:
                vc = 0
            lvd = str((r or {}).get("last_visit_date") or "").strip()
            try:
                if (r or {}).get("collect_seq") is not None:
                    cseq = int((r or {}).get("collect_seq"))
                else:
                    cseq = int(idx)
            except Exception:
                cseq = int(idx)
            cur.execute(
                """
                INSERT INTO event_mentor_visits (
                    nickname, member_grade, visit_count, last_visit_date, collect_seq, updated_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(nickname, member_grade) DO UPDATE SET
                    visit_count = excluded.visit_count,
                    last_visit_date = excluded.last_visit_date,
                    collect_seq = excluded.collect_seq,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (nick, grade, vc, lvd, cseq),
            )
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def get_event_mentor_visits_count(db_path: str) -> int:
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM event_mentor_visits")
        n = cur.fetchone()[0] or 0
        conn.close()
        return int(n)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 0

