import sqlite3
import os

DB_PATH = os.path.join('src', 'instance', 'hopaoems.sqlite')

def migrate():
    if not os.path.exists(DB_PATH):
        # Try alternate path
        alt_path = os.path.join('src', 'hopaoems', 'instance', 'hopaoems.sqlite')
        if os.path.exists(alt_path):
            print(f"Found DB at {alt_path}")
            db_path = alt_path
        else:
            print(f"DB not found at {DB_PATH} or {alt_path}")
            return
    else:
        db_path = DB_PATH

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1. Create wash_sessions
    print("Creating table wash_sessions...")
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
    
    # 2. Add wash_session_id to production_logs
    try:
        c.execute('ALTER TABLE production_logs ADD COLUMN wash_session_id INTEGER REFERENCES wash_sessions(id)')
        print("Added wash_session_id column.")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e):
             print("Column wash_session_id already exists.")
        else:
             print(f"Error adding column: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    migrate()
