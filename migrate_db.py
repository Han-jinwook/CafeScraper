"""
DB 스키마 마이그레이션: comments 테이블에 is_target 컬럼 추가
"""
import sqlite3
import os
import sys

# UTF-8 출력 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

def migrate_db():
    db_path = "cafe_data.db"
    
    if not os.path.exists(db_path):
        print(f"[ERROR] DB 파일이 없습니다: {db_path}")
        return
    
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    
    try:
        # 1. comments 테이블에 is_target 컬럼이 있는지 확인
        cursor.execute("PRAGMA table_info(comments)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_target' in columns:
            print("[OK] is_target 컬럼이 이미 존재합니다.")
        else:
            # 2. is_admin 컬럼이 있으면 이름 변경, 없으면 새로 추가
            if 'is_admin' in columns:
                print("[MIGRATE] is_admin -> is_target 으로 변경 중...")
                # SQLite는 컬럼 이름 변경을 직접 지원하지 않으므로 테이블 재생성
                cursor.execute("""
                    CREATE TABLE comments_new (
                        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        post_id TEXT,
                        writer_id TEXT,
                        nickname TEXT,
                        content TEXT,
                        is_target INTEGER,
                        FOREIGN KEY (post_id) REFERENCES posts (post_id)
                    )
                """)
                
                # 기존 데이터 복사 (is_admin → is_target)
                cursor.execute("""
                    INSERT INTO comments_new (comment_id, post_id, writer_id, nickname, content, is_target)
                    SELECT comment_id, post_id, writer_id, nickname, content, is_admin
                    FROM comments
                """)
                
                # 기존 테이블 삭제 후 이름 변경
                cursor.execute("DROP TABLE comments")
                cursor.execute("ALTER TABLE comments_new RENAME TO comments")
                
                print("[OK] is_admin -> is_target 변경 완료!")
            else:
                # is_admin도 없으면 새로 추가
                print("[ADD] is_target 컬럼 추가 중...")
                cursor.execute("ALTER TABLE comments ADD COLUMN is_target INTEGER DEFAULT 0")
                print("[OK] is_target 컬럼 추가 완료!")
        
        conn.commit()
        print(f"[SUCCESS] 마이그레이션 완료: {os.path.abspath(db_path)}")
        
    except Exception as e:
        print(f"[ERROR] 마이그레이션 실패: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
