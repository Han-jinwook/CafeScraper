import os, glob
import sqlite3

db_dir = os.path.expanduser(r'~\Documents\MarketingMonster\CafeScraper\DB')
dbs = glob.glob(os.path.join(db_dir, '*.db'))
if dbs:
    dbs.sort(key=os.path.getmtime, reverse=True)
    print('Latest DB:', dbs[0])
    conn = sqlite3.connect(dbs[0])
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print('Tables:', tables)
    
    for table in ['staff', 'cafe_staff', 'staffs', 'staff_data']:
        if table in tables:
            cursor.execute(f"SELECT * FROM {table}")
            print(f"--- {table} ---")
            print(cursor.fetchall())
            
    # Also dump some other tables
    if 'cafe_data' in tables:
        pass
else:
    print('No DB found.')
