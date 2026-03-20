import sqlite3
from werkzeug.security import generate_password_hash
from . import db

def init_schema():
    """Create tables if they don't exist, matching the production schema contract."""
    # print("--- [DB] Initializing Schema ---")
    
    # 1. Users
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('operator', 'viewer')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Fabrics
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS fabrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fabric_code TEXT UNIQUE NOT NULL,
            material TEXT,
            width_cm REAL,
            yard_weight_gyd REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migration: Add width_mm to fabrics if not exists (Idempotent)
    columns = [col[1] for col in db.query_db("PRAGMA table_info(fabrics)")]
    if 'width_mm' not in columns:
        db.execute_db("ALTER TABLE fabrics ADD COLUMN width_mm REAL")
        db.commit()

    # Migration: Add remark to fabrics if not exists (Idempotent)
    columns = [col[1] for col in db.query_db("PRAGMA table_info(fabrics)")]
    if 'remark' not in columns:
        db.execute_db("ALTER TABLE fabrics ADD COLUMN remark TEXT")
        db.commit()

    # 3. Cylinders
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS cylinders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fabric_id INTEGER NOT NULL,
            cylinder_no TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (fabric_id) REFERENCES fabrics (id)
        )
    ''')

    # 4. Rolls
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS rolls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cylinder_id INTEGER NOT NULL,
            roll_no TEXT NOT NULL,
            length_m REAL NOT NULL,
            weight_kg REAL,
            status TEXT NOT NULL DEFAULT 'in_stock',
            remark TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (cylinder_id) REFERENCES cylinders (id)
        )
    ''')

    # Migration: Add updated_at to rolls if not exists (Idempotent)
    columns = [col[1] for col in db.query_db("PRAGMA table_info(rolls)")]
    if 'updated_at' not in columns:
        # SQLite restriction: Cannot add column with non-constant default like CURRENT_TIMESTAMP
        db.execute_db("ALTER TABLE rolls ADD COLUMN updated_at TIMESTAMP")
        
        # Backfill existing data
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Priority: updated_at (null) -> created_at -> python_now
        db.execute_db("UPDATE rolls SET updated_at = COALESCE(created_at, ?)", (now_str,))
        db.commit()

    # Migration: Add remark to rolls if not exists (Idempotent)
    columns = [col[1] for col in db.query_db("PRAGMA table_info(rolls)")]
    if 'remark' not in columns:
        db.execute_db("ALTER TABLE rolls ADD COLUMN remark TEXT")
        db.commit()

    # Migration: Add unique constraint on cylinder_id and roll_no
    db.execute_db("CREATE UNIQUE INDEX IF NOT EXISTS idx_rolls_cylinder_roll ON rolls(cylinder_id, roll_no)")
    db.commit()

    # 5. Roll History
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS roll_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            old_qty REAL,
            new_qty REAL,
            delta REAL,
            source TEXT,
            note TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (roll_id) REFERENCES rolls (id)
        )
    ''')

    # 6. Samples
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_no TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            remark TEXT,
            fabric_no TEXT,
            sales_code TEXT,
            version TEXT,
            date_received TEXT,
            source_filename TEXT,
            source_mime TEXT,
            source_path TEXT,
            preview_path TEXT,
            preview_mime TEXT,
            preview_size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migration: Ensure asset columns exist in samples (Idempotent)
    columns = [col[1] for col in db.query_db("PRAGMA table_info(samples)")]
    asset_cols = [
        ('source_filename', 'TEXT'),
        ('source_mime', 'TEXT'),
        ('source_path', 'TEXT'),
        ('preview_path', 'TEXT'),
        ('preview_mime', 'TEXT'),
        ('preview_size', 'INTEGER'),
        ('version', 'TEXT'),
        ('printing_environment', 'TEXT'),
        ('printing_file_name', 'TEXT'),
        ('remark', 'TEXT')
    ]
    for col_name, col_type in asset_cols:
        if col_name not in columns:
            db.execute_db(f"ALTER TABLE samples ADD COLUMN {col_name} {col_type}")
    
    # 7. Sample Color Map
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS sample_color_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id INTEGER NOT NULL,
            pick_x INTEGER,
            pick_y INTEGER,
            rgb_r INTEGER,
            rgb_g INTEGER,
            rgb_b INTEGER,
            hex TEXT,
            note TEXT,
            target_mode TEXT DEFAULT 'note',
            target_l REAL,
            target_a REAL,
            target_b REAL,
            target_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sample_id) REFERENCES samples (id)
        )
    ''')

    # Migration: Refactor sample_color_map to Contract (Rebuild & Move)
    columns = [col[1] for col in db.query_db("PRAGMA table_info(sample_color_map)")]
    if 'r' in columns or 'target_b2' in columns:
        print("[MIGRATION] Rebuilding sample_color_map to align with contract (rgb_r/g/b, target_b)...")
        # 1. Create temporary table
        db.execute_db('''
            CREATE TABLE sample_color_map_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id INTEGER NOT NULL,
                pick_x INTEGER,
                pick_y INTEGER,
                rgb_r INTEGER,
                rgb_g INTEGER,
                rgb_b INTEGER,
                hex TEXT,
                note TEXT,
                target_mode TEXT DEFAULT 'note',
                target_l REAL,
                target_a REAL,
                target_b REAL,
                target_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sample_id) REFERENCES samples (id)
            )
        ''')
        # 2. Migrate data
        # Handle r -> rgb_r, target_b2 -> target_b
        # Map old names if they exist, otherwise use null
        r_col = 'r' if 'r' in columns else 'rgb_r'
        g_col = 'g' if 'g' in columns else 'rgb_g'
        b_col = 'b' if 'b' in columns else 'rgb_b'
        target_b_col = 'target_b2' if 'target_b2' in columns else 'target_b'
        
        db.execute_db(f'''
            INSERT INTO sample_color_map_new (
                id, sample_id, pick_x, pick_y, rgb_r, rgb_g, rgb_b, hex, note,
                target_mode, target_l, target_a, target_b, target_note, created_at
            ) SELECT 
                id, sample_id, pick_x, pick_y, {r_col}, {g_col}, {b_col}, hex, note,
                target_mode, target_l, target_a, {target_b_col}, target_note, created_at
            FROM sample_color_map
        ''')
        # 3. Swap tables
        db.execute_db("DROP TABLE sample_color_map")
        db.execute_db("ALTER TABLE sample_color_map_new RENAME TO sample_color_map")
        db.commit()

    # Ensure target columns exist in sample_color_map (Idempotent for new columns in contract)
    columns = [col[1] for col in db.query_db("PRAGMA table_info(sample_color_map)")]
    target_cols = [
        ('target_mode', "TEXT DEFAULT 'note'"),
        ('target_l', 'REAL'),
        ('target_a', 'REAL'),
        ('target_b', 'REAL'),
        ('target_note', 'TEXT'),
        ('rgb_r', 'INTEGER'),
        ('rgb_g', 'INTEGER'),
        ('rgb_b', 'INTEGER')
    ]
    for col_name, col_type in target_cols:
        if col_name not in columns:
            db.execute_db(f"ALTER TABLE sample_color_map ADD COLUMN {col_name} {col_type}")

    # 8. Inks
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS inks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            type TEXT,
            color TEXT,
            qty REAL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 9. Orders
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE NOT NULL,
            received_date TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'pending',
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')

    # 10. Order Items
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            fabric_no TEXT,
            sample_id INTEGER,
            qty REAL,
            note TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (sample_id) REFERENCES samples (id)
        )
    ''')

    # 11. Production Tasks
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS production_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            order_item_id INTEGER UNIQUE,
            sample_id INTEGER,
            fabric_no TEXT,
            target_qty REAL,
            used_length REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (order_item_id) REFERENCES order_items (id),
            FOREIGN KEY (sample_id) REFERENCES samples (id)
        )
    ''')

    # Migration: Add order_item_id to production_tasks if not exists (Idempotent)
    columns = [col[1] for col in db.query_db("PRAGMA table_info(production_tasks)")]
    if 'order_item_id' not in columns:
        db.execute_db("ALTER TABLE production_tasks ADD COLUMN order_item_id INTEGER")
        db.commit()
        # Note: We don't add UNIQUE constraint via ALTER TABLE as SQLite doesn't support it easily.
        # But for new tables, it is enforced by CREATE TABLE.

    # 12. Production Logs
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS production_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            roll_id INTEGER NOT NULL,
            length REAL NOT NULL,
            note TEXT,
            roll_depleted INTEGER DEFAULT 0,
            washed_at TIMESTAMP,
            wash_session_id INTEGER,
            operator_id INTEGER,
            status TEXT DEFAULT 'unwashed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES production_tasks (id),
            FOREIGN KEY (roll_id) REFERENCES rolls (id),
            FOREIGN KEY (operator_id) REFERENCES users (id),
            FOREIGN KEY (wash_session_id) REFERENCES wash_sessions (id)
        )
    ''')
    # Migration: Add wash_session_id to production_logs if not exists (Idempotent)
    columns = [col[1] for col in db.query_db("PRAGMA table_info(production_logs)")]
    if 'wash_session_id' not in columns:
        db.execute_db("ALTER TABLE production_logs ADD COLUMN wash_session_id INTEGER")
        db.commit()


    # 14. Wash Sessions
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS wash_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vat_code TEXT NOT NULL,
            roll_count INTEGER NOT NULL,
            total_length REAL NOT NULL,
            operator_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (operator_id) REFERENCES users (id)
        )
    ''')
    
    # Migration: Add operator_id to wash_sessions if not exists (Idempotent)
    # Handles old DBs that had created_by instead of operator_id
    ws_columns = [col[1] for col in db.query_db("PRAGMA table_info(wash_sessions)")]
    if 'operator_id' not in ws_columns:
        db.execute_db("ALTER TABLE wash_sessions ADD COLUMN operator_id INTEGER")
        db.commit()

    # 16. Audit Logs
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operator_id INTEGER,
            action TEXT NOT NULL,
            target_entity TEXT,
            target_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,
            FOREIGN KEY (operator_id) REFERENCES users (id)
        )
    ''')

    # 17. Image Vectors (AI Phase 3: 圖片入庫 + 以圖搜圖)
    db.execute_db('''
        CREATE TABLE IF NOT EXISTS image_vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            ocr_data TEXT,
            embedding BLOB NOT NULL,
            embedding_dim INTEGER NOT NULL,
            created_at DATETIME DEFAULT (datetime('now'))
        )
    ''')

    db.commit()

    # 15. Role Consolidation Migration
    # Migrate 'admin' to 'operator', then ensure all others are 'viewer'
    db.execute_db("UPDATE users SET role = 'operator' WHERE role = 'admin' OR role = 'op' OR role = 'Operator'")
    db.execute_db("UPDATE users SET role = 'viewer' WHERE role NOT IN ('operator', 'viewer')")
    db.commit()

    # Seed default admin if not exists
    admin = db.query_db("SELECT id FROM users WHERE username = 'admin'", one=True)
    if not admin:
        db.execute_db(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ('admin', generate_password_hash('admin'), 'operator')
        )
        db.commit()
        print("--- [INITIALIZATION] ---")
        print("Default operator created: admin / admin")
        
    # Seed default viewer if not exists
    viewer = db.query_db("SELECT id FROM users WHERE username = 'viewer'", one=True)
    if not viewer:
        db.execute_db(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ('viewer', generate_password_hash('viewer'), 'viewer')
        )
        db.commit()
        print("Default viewer created: viewer / viewer")

    print("-------------------------")
