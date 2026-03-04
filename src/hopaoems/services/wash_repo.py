from .db import query_db, execute_db, get_db
from . import production_repo, audit_service
from datetime import datetime

def list_unwashed_logs():
    """
    List all production logs that are not yet washed (washed_at IS NULL).
    Returns flat list ordered by vat_code.
    """
    return query_db('''
        SELECT pl.*, 
               u.username as operator_name, 
               r.roll_no,
               o.order_no,
               COALESCE(c.cylinder_no, '') as vat_code,
               f.fabric_code,
               s.title as sample_title,
               s.preview_path
        FROM production_logs pl
        LEFT JOIN production_tasks pt ON pl.task_id = pt.id
        LEFT JOIN orders o ON pt.order_id = o.id
        LEFT JOIN samples s ON pt.sample_id = s.id
        LEFT JOIN rolls r ON pl.roll_id = r.id
        LEFT JOIN cylinders c ON r.cylinder_id = c.id
        LEFT JOIN fabrics f ON c.fabric_id = f.id
        LEFT JOIN users u ON pl.operator_id = u.id
        WHERE pl.washed_at IS NULL
        ORDER BY COALESCE(c.cylinder_no, ''), pl.created_at ASC
    ''')

def get_wash_list_data():
    """
    Groups pending logs by vat_code and calculates totals.
    """
    logs = list_unwashed_logs()
    
    groups = []
    current_vat = None
    current_group = None
    
    unique_rolls_all = set()
    total_length_all = 0.0
    vats_all = set()
    
    for log in logs:
        log = dict(log)
        vat = log['vat_code']
        
        # Track global stats
        if vat:
            vats_all.add(vat)
        unique_rolls_all.add(log['roll_id'])
        total_length_all += float(log['length'])
        
        if vat != current_vat:
            if current_group:
                groups.append(current_group)
            current_vat = vat
            current_group = {
                'vat_code': vat,
                'logs': [],
                'unique_rolls': set(),
                'total_length': 0.0,
                'is_missing_vat': not vat
            }
        
        current_group['logs'].append(log)
        current_group['unique_rolls'].add(log['roll_id'])
        current_group['total_length'] += float(log['length'])
        
    if current_group:
        groups.append(current_group)
        
    # Finalize groups
    for g in groups:
        g['roll_count'] = len(g['unique_rolls'])
        g['total_length'] = round(g['total_length'], 2)
        
    return {
        'groups': groups,
        'stats': {
            'vat_count': len(vats_all),
            'unique_roll_count': len(unique_rolls_all),
            'total_length': round(total_length_all, 2)
        }
    }

def create_wash_session(vat_code, log_ids, operator_id):
    """
    Create a wash session for the selected logs.
    """
    db = get_db()
    c = db.cursor()
    try:
        # Calculate stats from logs
        question_marks = ','.join(['?']*len(log_ids))
        c.execute(f'''
            SELECT COUNT(DISTINCT roll_id), SUM(length) 
            FROM production_logs 
            WHERE id IN ({question_marks})
        ''', log_ids)
        row = c.fetchone()
        roll_count = row[0] or 0
        total_length = row[1] or 0
        
        # Create Session
        c.execute('''
            INSERT INTO wash_sessions (vat_code, roll_count, total_length, operator_id)
            VALUES (?, ?, ?, ?)
        ''', (vat_code, roll_count, total_length, operator_id))
        session_id = c.lastrowid
        
        # Update Logs
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute(f'''
            UPDATE production_logs 
            SET washed_at = ?, wash_session_id = ? 
            WHERE id IN ({question_marks})
        ''', (now_str, session_id, *log_ids))
        
        # 3. Trigger Maintenance for affected tasks
        task_rows = query_db(f"SELECT DISTINCT task_id FROM production_logs WHERE id IN ({question_marks})", log_ids)
        for row in task_rows:
            production_repo.sync_status_pullback(row['task_id'], c)
            
        db.commit()
        return session_id
    except Exception as e:
        db.rollback()
        raise e

def list_visible_sessions_paginated(search_query=None, limit=50, offset=0):
    visible_task_ids = production_repo.list_visible_task_ids()
    if not visible_task_ids:
        return []
    
    question_marks = ','.join(['?']*len(visible_task_ids))
    params = list(visible_task_ids)
    
    query = f'''
        SELECT ws.*, u.username as operator_name
        FROM wash_sessions ws
        LEFT JOIN users u ON ws.operator_id = u.id
        WHERE EXISTS (
            SELECT 1 FROM production_logs pl 
            WHERE pl.wash_session_id = ws.id 
            AND pl.task_id IN ({question_marks})
    '''
    
    if search_query:
        query += f''' AND (
            ws.vat_code LIKE ? OR 
            pl.roll_id LIKE ? OR 
            pl.task_id LIKE ? 
        )'''
        sq = f"%{search_query}%"
        params.extend([sq, sq, sq])
        
    query += ") ORDER BY ws.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    rows = query_db(query, params)
    return [dict(r) for r in rows]

def count_visible_sessions(search_query=None):
    visible_task_ids = production_repo.list_visible_task_ids()
    if not visible_task_ids:
        return 0
    
    question_marks = ','.join(['?']*len(visible_task_ids))
    params = list(visible_task_ids)
    
    query = f'''
        SELECT COUNT(*) as cnt
        FROM wash_sessions ws
        WHERE EXISTS (
            SELECT 1 FROM production_logs pl 
            WHERE pl.wash_session_id = ws.id 
            AND pl.task_id IN ({question_marks})
    '''
    
    if search_query:
        query += f''' AND (
            ws.vat_code LIKE ? OR 
            pl.roll_id LIKE ? OR 
            pl.task_id LIKE ? 
        )'''
        sq = f"%{search_query}%"
        params.extend([sq, sq, sq])
        
    query += ")"
    res = query_db(query, params, one=True)
    return res['cnt'] if res else 0

def list_visible_sessions(search_query=None):
    return list_visible_sessions_paginated(search_query, limit=100, offset=0)

def get_session_by_id(session_id):
    """Fetch a single wash session by ID."""
    return query_db('''
        SELECT ws.*, u.username as operator_name
        FROM wash_sessions ws
        LEFT JOIN users u ON ws.operator_id = u.id
        WHERE ws.id = ?
    ''', (session_id,), one=True)

def get_session_logs(session_id):
    """Get logs for a session (for expansion)."""
    return query_db('''
        SELECT pl.*, r.roll_no, s.title as sample_title, s.preview_path, 
               o.order_no, f.fabric_code
        FROM production_logs pl
        LEFT JOIN rolls r ON pl.roll_id = r.id
        LEFT JOIN production_tasks pt ON pl.task_id = pt.id
        LEFT JOIN samples s ON pt.sample_id = s.id
        LEFT JOIN orders o ON pt.order_id = o.id
        LEFT JOIN cylinders c ON r.cylinder_id = c.id
        LEFT JOIN fabrics f ON c.fabric_id = f.id
        WHERE pl.wash_session_id = ?
    ''', (session_id,))

def revoke_session(session_id):
    """
    Revoke a wash session by undoing every log in it.
    This ensures unified maintenance/pullback logic.
    """
    logs = get_session_logs(session_id)
    for log in logs:
        undo_log(log['id'])
    
    # Audit Log
    from flask import g
    audit_service.log_event(g.user['id'] if g and hasattr(g, 'user') and g.user else 0, 
                            'REVOKE_SESSION', 'wash_sessions', session_id)

    # Finally delete the session record itself
    execute_db('DELETE FROM wash_sessions WHERE id = ?', (session_id,))

def undo_log(log_id):
    """
    Undo wash for a single log (complete erasure).
    Sets washed_at = NULL and wash_session_id = NULL.
    Pull back task status to 'printing' if it was 'done'.
    """
    db = get_db()
    c = db.cursor()
    try:
        # Get task_id for the log
        log = query_db("SELECT task_id FROM production_logs WHERE id = ?", (log_id,), one=True)
        if not log:
            return
        task_id = log['task_id']

        # 1. Reset log wash status
        c.execute('UPDATE production_logs SET washed_at = NULL, wash_session_id = NULL WHERE id = ?', (log_id,))
        
        # 2. Trigger Maintenance
        production_repo.sync_status_pullback(task_id, c)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def get_log_for_undo(log_id):
    """Get log details for undo confirmation."""
    return query_db('''
        SELECT pl.*, 
               r.roll_no,
               COALESCE(c.cylinder_no, '(UNKNOWN)') as vat_code,
               s.title as sample_title,
               s.sample_no,
               s.id as sample_id
        FROM production_logs pl
        LEFT JOIN rolls r ON pl.roll_id = r.id
        LEFT JOIN cylinders c ON r.cylinder_id = c.id
        LEFT JOIN production_tasks pt ON pl.task_id = pt.id
        LEFT JOIN samples s ON pt.sample_id = s.id
        WHERE pl.id = ?
    ''', (log_id,), one=True)
