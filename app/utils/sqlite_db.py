import sqlite3
import os

def init_db(db_path="cafe_data.db"):
    """Project DAYBREAK 전용 SQLite 데이터베이스 초기화"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

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
    print(f"✅ DB 초기화 완료: {os.path.abspath(db_path)}")

if __name__ == "__main__":
    init_db()
