
import os
import sqlite3
from flask import g, current_app

def get_db():
    if 'db' not in g:
        db_path = current_app.config['DATABASE']
        # Use check_same_thread=False for test environments
        check_same_thread = not current_app.config.get('TESTING', False)
        g.db = sqlite3.connect(db_path, check_same_thread=check_same_thread)
        g.db.row_factory = sqlite3.Row
        
        # Startup debug: Log DB path and wash_sessions columns (first connection only)
        if not getattr(current_app, '_db_startup_logged', False):
            print(f"[DB STARTUP] Using database: {db_path}")
            try:
                cur = g.db.execute("PRAGMA table_info(wash_sessions)")
                cols = [row[1] for row in cur.fetchall()]
                print(f"[DB STARTUP] wash_sessions columns: {cols}")
            except Exception as e:
                print(f"[DB STARTUP] wash_sessions check failed: {e}")
            current_app._db_startup_logged = True
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_app(app):
    app.teardown_appcontext(close_db)

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def commit():
    get_db().commit()

def execute_db(query, args=(), commit=True):
    db = get_db()
    cur = db.execute(query, args)
    if commit:
        db.commit()
    return cur.lastrowid
