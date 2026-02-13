import sqlite3
import os

def init_db(db_path="cafe_data.db"):
    """Project DAYBREAK 전용 SQLite 데이터베이스 초기화"""
    # 다른 앱과 같은 DB를 동시에 쓸 수 있으므로:
    # - WAL 모드로 동시 읽기/쓰기 충돌을 줄이고
    # - busy_timeout으로 잠금 대기 시간을 확보
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        # 일부 환경에서 PRAGMA가 실패해도 테이블 생성은 진행
        pass

    # 게시글 테이블 (posts)
    # member_id는 네이버에서 제공하는 고유 ID가 있을 경우 저장, 없으면 nickname으로 대체 가능
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            post_id TEXT PRIMARY KEY,
            member_id TEXT,
            nickname TEXT,
            title TEXT,
            content TEXT,
            date TEXT,
            board_name TEXT,
            category TEXT,
            view_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            member_level TEXT,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 구버전 DB 호환(컬럼 추가)
    try:
        cursor.execute("PRAGMA table_info(posts)")
        cols = [row[1] for row in cursor.fetchall()]
        if "category" not in cols:
            cursor.execute("ALTER TABLE posts ADD COLUMN category TEXT DEFAULT ''")
        if "view_count" not in cols:
            cursor.execute("ALTER TABLE posts ADD COLUMN view_count INTEGER DEFAULT 0")
        if "like_count" not in cols:
            cursor.execute("ALTER TABLE posts ADD COLUMN like_count INTEGER DEFAULT 0")
        if "member_level" not in cols:
            cursor.execute("ALTER TABLE posts ADD COLUMN member_level TEXT DEFAULT ''")
    except Exception:
        pass

    # 댓글 테이블 (comments)
    # is_target: 수집 대상 여부 (1: 본문 작성자 or 운영자, 0: 기타)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT,
            writer_id TEXT,
            nickname TEXT,
            content TEXT,
            is_target INTEGER,
            FOREIGN KEY (post_id) REFERENCES posts (post_id)
        )
    ''')

    # VitaminDWiki papers 테이블 (전수 조사 모드)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS papers (
            url TEXT PRIMARY KEY,
            title TEXT,
            summary TEXT,
            content TEXT,
            category TEXT,
            collected_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    # print(f"✅ DB 초기화 완료: {os.path.abspath(db_path)}")

if __name__ == "__main__":
    init_db()
