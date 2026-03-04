
import json
import os
from flask import current_app
from .db import query_db, execute_db

def list_inks_paginated(limit=50, offset=0, q=None):
    if q:
        search = f"%{q}%"
        return query_db('SELECT * FROM inks WHERE type LIKE ? OR color LIKE ? ORDER BY date DESC LIMIT ? OFFSET ?', (search, search, limit, offset))
    return query_db('SELECT * FROM inks ORDER BY date DESC LIMIT ? OFFSET ?', (limit, offset))

def count_inks(q=None):
    if q:
        search = f"%{q}%"
        res = query_db('SELECT COUNT(*) as cnt FROM inks WHERE type LIKE ? OR color LIKE ?', (search, search), one=True)
    else:
        res = query_db('SELECT COUNT(*) as cnt FROM inks', (), one=True)
    return res['cnt'] if res else 0

def list_inks():
    ensure_migration()
    return list_inks_paginated(limit=1000, offset=0)

def get_ink(id):
    return query_db('SELECT * FROM inks WHERE id = ?', (id,), one=True)

def create_ink(date, type, color, qty, note):
    return execute_db(
        'INSERT INTO inks (date, type, color, qty, note) VALUES (?, ?, ?, ?, ?)',
        (date, type, color, qty, note)
    )

def update_ink(id, date, type, color, qty, note):
    execute_db(
        'UPDATE inks SET date=?, type=?, color=?, qty=?, note=? WHERE id=?',
        (date, type, color, qty, note, id)
    )

def delete_ink(id):
    execute_db('DELETE FROM inks WHERE id = ?', (id,))

def ensure_migration():
    """Migrate from JSON if table is empty and JSON exists."""
    count = query_db('SELECT COUNT(*) as c FROM inks', one=True)['c']
    if count > 0:
        return

    # Check for legacy data file
    # Assuming legacy path is source_root/../src/data/inks.json relative to this file?
    # No, app.root_path is src/hopaoems. Old data is in src/data.
    # So we need to go up two levels from app.root_path then down to src/data?
    # Let's try absolute path based on known structure or relative to instance.
    # Actually, the user environment says: c:\Users\JingHu\Desktop\hopaoems\src\data
    
    # We can try to locate it relative to current_app.root_path
    # current_app.root_path is .../src/hopaoems
    base_dir = os.path.dirname(os.path.dirname(current_app.root_path)) # up to src then up to root?
    # No, src/hopaoems (package) is the root_path.
    # src/ is parent. root is parent of src.
    # So base_dir = root of project.
    
    # Let's assume standard path: ../../data/inks.json relative to this file
    # this file is src/hopaoems/services/ink_repo.py
    
    legacy_path = os.path.normpath(os.path.join(current_app.root_path, '..', 'data', 'inks.json'))
    
    if os.path.exists(legacy_path):
        try:
            with open(legacy_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        create_ink(
                            item.get('date'),
                            item.get('type'),
                            item.get('color'),
                            item.get('qty'),
                            item.get('note')
                        )
        except Exception as e:
            # Log error but don't crash app
            print(f"Migration failed: {e}")
