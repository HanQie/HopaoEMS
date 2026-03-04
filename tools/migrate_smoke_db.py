import sqlite3
import os

DB_PATH = os.path.join('src', 'hopaoems', 'instance', 'hopaoems_smoke_test.sqlite')
ALT_PATH = os.path.join('src', 'instance', 'hopaoems_smoke_test.sqlite')

def migrate(path):
    if not os.path.exists(path):
        print(f"Skipping {path} (not found)")
        return
    
    print(f"Migrating {path}...")
    conn = sqlite3.connect(path)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS wash_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vat_code TEXT,
            roll_count INTEGER DEFAULT 0,
            total_length REAL DEFAULT 0,
            meta TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER
        )
    ''')
    
    try:
        c.execute('ALTER TABLE production_logs ADD COLUMN wash_session_id INTEGER REFERENCES wash_sessions(id)')
        print("Added wash_session_id column.")
    except sqlite3.OperationalError:
        print("Column wash_session_id already exists.")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate(DB_PATH)
    migrate(ALT_PATH)
