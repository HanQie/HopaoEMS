from .db import query_db, execute_db, get_db
from . import fabric_repo, audit_service
from datetime import datetime

def list_visible_task_ids():
    """Returns a list of IDs for tasks that are not done or canceled."""
    rows = query_db("SELECT id FROM production_tasks WHERE status NOT IN ('done', 'canceled')")
    return [r['id'] for r in rows]

def sync_status_pullback(task_id, cursor=None):
    """
    Unified maintenance for task/order status pullback.
    Rule 1: Task with unwashed logs cannot be 'done'.
    Rule 2: Order status is calculated based on all tasks and logs.
    """
    c = cursor or get_db().cursor()
    
    # 1. Check for unwashed logs for this specific task
    row = query_db("SELECT COUNT(*) as c FROM production_logs WHERE task_id = ? AND washed_at IS NULL", (task_id,), one=True)
    unwashed_count = row['c'] if row else 0
    
    if unwashed_count > 0:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Pull back task to 'printing' if it was 'done'
        c.execute('''
            UPDATE production_tasks 
            SET status = 'printing', updated_at = ? 
            WHERE id = ? AND status = 'done'
        ''', (now_str, task_id))
    
    # 2. Sync parent Order status
    # Get the order_id for this task
    task = query_db("SELECT order_id FROM production_tasks WHERE id = ?", (task_id,), one=True)
    if task and task['order_id']:
        from . import order_repo
        order_repo.sync_order_status(task['order_id'], cursor=c)

def get_dashboard_stats(limit_recent_logs=10):
    """Get high level stats for dashboard."""
    # 1. Open Orders
    open_orders = query_db("SELECT COUNT(*) as c FROM orders WHERE status = 'open'", one=True)['c']
    
    # 2. Printing Tasks
    printing_tasks = query_db("SELECT COUNT(*) as c FROM production_tasks WHERE status = 'printing'", one=True)['c']
    
    # 3. Inventory Total (in_stock)
    inventory_total = query_db("SELECT SUM(length_m) as s FROM rolls WHERE status = 'in_stock'", one=True)['s'] or 0
    
    # 4. Unwashed Logs
    unwashed_count = query_db("SELECT COUNT(*) as c FROM production_logs WHERE washed_at IS NULL", one=True)['c']
    
    # 5. Recent Logs
    recent_logs = query_db('''
        SELECT pl.*, 
               u.username as operator_name, 
               r.roll_no, 
               c.cylinder_no,
               s.preview_path, 
               s.title as sample_title,
               o.order_no,
               pt.fabric_no
        FROM production_logs pl
        LEFT JOIN users u ON pl.operator_id = u.id
        LEFT JOIN rolls r ON pl.roll_id = r.id
        LEFT JOIN cylinders c ON r.cylinder_id = c.id
        LEFT JOIN production_tasks pt ON pl.task_id = pt.id
        LEFT JOIN samples s ON pt.sample_id = s.id
        LEFT JOIN orders o ON pt.order_id = o.id
        ORDER BY pl.created_at DESC
        LIMIT ?
    ''', (limit_recent_logs,))
    
    return {
        'active_tasks': printing_tasks,
        'open_orders_count': open_orders,
        'inventory_total_length_m': round(inventory_total or 0, 2),
        'unwashed_logs_count': unwashed_count,
        'recent_logs': recent_logs,
        'links': {
            'open_orders': '/order/?status=active',
            'printing_tasks': '/production/',
            'inventory': '/fabric/',
            'unwashed_logs': '/wash/'
        }
    }

def list_active_tasks_paginated(limit=50, offset=0):
    return query_db('''
        SELECT pt.*, 
               o.order_no,
               s.title as sample_title,
               s.preview_path,
               pt.target_qty as target,
               COALESCE(stats.log_count, 0) as log_count,
               COALESCE(stats.printed, 0) as printed,
               COALESCE(stats.to_wash, 0) as to_wash,
               COALESCE(stats.washed, 0) as washed,
               COALESCE(stats.unwashed_count, 0) as unwashed_count
        FROM production_tasks pt
        LEFT JOIN orders o ON pt.order_id = o.id
        LEFT JOIN samples s ON pt.sample_id = s.id
        LEFT JOIN (
            SELECT 
                task_id,
                COUNT(*) as log_count,
                SUM(length) as printed,
                SUM(CASE WHEN washed_at IS NULL THEN length ELSE 0 END) as to_wash,
                SUM(CASE WHEN washed_at IS NOT NULL THEN length ELSE 0 END) as washed,
                COUNT(CASE WHEN washed_at IS NULL THEN 1 END) as unwashed_count
            FROM production_logs
            GROUP BY task_id
        ) stats ON pt.id = stats.task_id
        WHERE pt.status = 'printing'
        ORDER BY pt.id DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))

def count_active_tasks():
    res = query_db("SELECT COUNT(*) as cnt FROM production_tasks WHERE status = 'printing'", one=True)
    return res['cnt'] if res else 0

def list_active_tasks():
    return list_active_tasks_paginated(limit=200, offset=0)

def get_task(task_id):
    """Get task by ID with related info."""
    row = query_db('''
        SELECT pt.*, 
               o.order_no,
               s.title as sample_title,
               s.preview_path,
               s.version,
               s.source_filename,
               s.printing_file_name,
               pt.target_qty as target
        FROM production_tasks pt
        LEFT JOIN orders o ON pt.order_id = o.id
        LEFT JOIN samples s ON pt.sample_id = s.id
        WHERE pt.id = ?
    ''', (task_id,), one=True)
    return dict(row) if row else None

def get_task_with_progress(task_id):
    """Get task with progress stats."""
    task = get_task(task_id)
    if not task:
        return None
    
    # Calculate progress
    stats = query_db('''
        SELECT 
            COUNT(*) as log_count,
            COALESCE(SUM(length), 0) as printed,
            COALESCE(SUM(CASE WHEN washed_at IS NULL THEN length ELSE 0 END), 0) as to_wash,
            COALESCE(SUM(CASE WHEN washed_at IS NOT NULL THEN length ELSE 0 END), 0) as washed,
            COUNT(CASE WHEN washed_at IS NULL THEN 1 END) as unwashed_count
        FROM production_logs
        WHERE task_id = ?
    ''', (task_id,), one=True)
    
    return {
        **dict(task),
        'log_count': stats['log_count'],
        'printed': stats['printed'],
        'to_wash': stats['to_wash'],
        'washed': stats['washed'],
        'unwashed_count': stats['unwashed_count'],
        'target': task['target_qty']
    }

def list_logs(task_id):
    """List production logs for a task, including sample and roll info."""
    return query_db('''
        SELECT pl.*, u.username as operator_name, r.roll_no, s.preview_path, s.title as sample_title,
               COALESCE(c.cylinder_no, '(UNKNOWN)') as vat_code
        FROM production_logs pl
        LEFT JOIN users u ON pl.operator_id = u.id
        LEFT JOIN rolls r ON pl.roll_id = r.id
        LEFT JOIN cylinders c ON r.cylinder_id = c.id
        LEFT JOIN production_tasks pt ON pl.task_id = pt.id
        LEFT JOIN samples s ON pt.sample_id = s.id
        WHERE pl.task_id = ?
        ORDER BY pl.created_at DESC
    ''', (task_id,))

def get_log_detail(log_id):
    """Get detailed log info for edit/delete operations."""
    return query_db('''
        SELECT pl.*, 
               u.username as operator_name, 
               r.roll_no,
               COALESCE(c.cylinder_no, '(UNKNOWN)') as vat_code,
               s.title as sample_title,
               s.preview_path
        FROM production_logs pl
        LEFT JOIN users u ON pl.operator_id = u.id
        LEFT JOIN rolls r ON pl.roll_id = r.id
        LEFT JOIN cylinders c ON r.cylinder_id = c.id
        LEFT JOIN production_tasks pt ON pl.task_id = pt.id
        LEFT JOIN samples s ON pt.sample_id = s.id
        WHERE pl.id = ?
    ''', (log_id,), one=True)

def _cleanup_wash_session(session_id, cursor):
    """
    Clean up wash session after implicit undo.
    Recalculates stats and deletes session if it has no logs left.
    """
    if not session_id:
        return
    
    # Check if session still has logs
    row = query_db(
        "SELECT COUNT(*) as c FROM production_logs WHERE wash_session_id = ?",
        (session_id,),
        one=True
    )
    log_count = row['c'] if row else 0
    
    if log_count == 0:
        # Delete empty session
        cursor.execute("DELETE FROM wash_sessions WHERE id = ?", (session_id,))
    else:
        # Recalculate session stats
        stats = query_db('''
            SELECT COUNT(DISTINCT roll_id) as roll_count, SUM(length) as total_length
            FROM production_logs
            WHERE wash_session_id = ?
        ''', (session_id,), one=True)
        
        cursor.execute('''
            UPDATE wash_sessions
            SET roll_count = ?, total_length = ?
            WHERE id = ?
        ''', (stats['roll_count'] or 0, stats['total_length'] or 0, session_id))

def check_log_lock(log_id):
    """
    Check if a production log is 'locked' (either washed or in a session).
    """
    log = query_db('SELECT washed_at, wash_session_id FROM production_logs WHERE id = ?', (log_id,), one=True)
    if not log:
        return False
    return (log['washed_at'] is not None or log['wash_session_id'] is not None)

def update_log(log_id, note, new_length=None, force_undo=False):
    """
    Update production log note and optionally length.
    Rules:
    1. Length changes on washed/locked logs are blocked unless force_undo=True.
    2. Note-only updates are always allowed.
    Returns: (success: bool, auto_undo_occurred: bool)
    """
    db = get_db()
    cursor = db.cursor()
    
    try:
        log = query_db('''
            SELECT pl.*, r.length_m as roll_length, r.id as roll_id
            FROM production_logs pl
            LEFT JOIN rolls r ON pl.roll_id = r.id
            WHERE pl.id = ?
        ''', (log_id,), one=True)
        
        if not log:
            raise ValueError("Log not found")
        
        old_length = log['length']
        task_id = log['task_id']
        roll_id = log['roll_id']
        
        is_locked = check_log_lock(log_id)
        old_session_id = log['wash_session_id']
        
        auto_undo_occurred = False
        # length_requested is True if the caller explicitly provided a new_length value
        length_requested = (new_length is not None)
        length_changed = (length_requested and abs(float(new_length) - old_length) > 1e-6)
        
        # Enforcement: Block length-changing updates if locked and not forced
        if length_requested and is_locked and not force_undo:
            raise ValueError("production.error.log_is_locked")
            
        if length_requested and is_locked and force_undo:
            auto_undo_occurred = True
            # Clean up session first
            if old_session_id:
                _cleanup_wash_session(old_session_id, cursor)
        
        # Update numerical stats if length changed
        if length_changed:
            new_len_float = float(new_length)
            roll_available_before = log['roll_length'] + old_length
            if new_len_float > roll_available_before:
                raise ValueError("production.log.edit.error.length_exceeds_roll")
            
            delta = new_len_float - old_length
            new_roll_length = roll_available_before - new_len_float
            roll_status = 'depleted' if new_roll_length == 0 else 'in_stock'
            
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                UPDATE rolls 
                SET length_m = ?, status = ?, updated_at = ?
                WHERE id = ?
            ''', (new_roll_length, roll_status, now_str, roll_id))
            
            cursor.execute('''
                UPDATE production_tasks
                SET used_length = used_length + ?, updated_at = ?
                WHERE id = ?
            ''', (delta, now_str, task_id))

        # Update log content (Explicitly clearing wash status if needed)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if auto_undo_occurred:
            cursor.execute('''
                UPDATE production_logs 
                SET note = ?, length = ?, washed_at = NULL, wash_session_id = NULL, updated_at = ?
                WHERE id = ?
            ''', (note, float(new_length), now_str, log_id))
        elif length_changed:
            cursor.execute('''
                UPDATE production_logs 
                SET note = ?, length = ?, updated_at = ?
                WHERE id = ?
            ''', (note, float(new_length), now_str, log_id))
        else:
            cursor.execute('''
                UPDATE production_logs 
                SET note = ?, updated_at = ?
                WHERE id = ?
            ''', (note, now_str, log_id))
        
        # Trigger status pullback
        sync_status_pullback(task_id, cursor)
        
        db.commit()
        return True, auto_undo_occurred
    except Exception as e:
        db.rollback()
        raise e

def delete_log(log_id):
    """
    Delete production log. 
    Rule: Block deletion if log is washed or locked.
    """
    db = get_db()
    cursor = db.cursor()
    
    try:
        log = query_db('''
            SELECT pl.*, r.id as roll_id
            FROM production_logs pl
            LEFT JOIN rolls r ON pl.roll_id = r.id
            WHERE pl.id = ?
        ''', (log_id,), one=True)
        
        if not log:
            raise ValueError("Log not found")
        
        if check_log_lock(log_id):
            raise ValueError("production.error.log_is_locked")

        task_id = log['task_id']
        roll_id = log['roll_id']
        length = log['length']
        
        # 1. Compensate roll
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE rolls
            SET length_m = length_m + ?, status = 'in_stock', updated_at = ?
            WHERE id = ?
        ''', (length, now_str, roll_id))

        # 2. Delete log
        cursor.execute("DELETE FROM production_logs WHERE id = ?", (log_id,))
        
        # 3. Adjust task used_length
        cursor.execute('''
            UPDATE production_tasks 
            SET used_length = used_length - ?, updated_at = ?
            WHERE id = ?
        ''', (length, now_str, task_id))
        
        # 4. Trigger Maintenance
        sync_status_pullback(task_id, cursor)
        
        # 5. Audit Log
        from flask import g
        audit_service.log_event(g.user['id'] if g and hasattr(g, 'user') and g.user else 0, 
                                'DELETE', 'production_logs', log_id, f"Length: {length}, Roll: {log_id}")

        db.commit()
        return True, False
    except Exception as e:
        db.rollback()
        raise e

def undo_log_wash(log_id):
    """
    Manual individual log wash undo. 
    Clears washed_at and wash_session_id, then triggers pullback.
    """
    db = get_db()
    cursor = db.cursor()
    try:
        log = query_db("SELECT id, task_id, wash_session_id FROM production_logs WHERE id = ?", (log_id,), one=True)
        if not log:
            raise ValueError("Log not found")
            
        task_id = log['task_id']
        session_id = log['wash_session_id']
        
        cursor.execute('''
            UPDATE production_logs 
            SET washed_at = NULL, wash_session_id = NULL 
            WHERE id = ?
        ''', (log_id,))
        
        if session_id:
            _cleanup_wash_session(session_id, cursor)
            
        sync_status_pullback(task_id, cursor)

        # Audit Log
        from flask import g
        audit_service.log_event(g.user['id'] if g and hasattr(g, 'user') and g.user else 0, 
                                'UNDO_WASH', 'production_logs', log_id)

        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def create_log(task_id, roll_id, length, note, operator_id, mark_depleted=False):
    """
    Produce Log + Optional Deplete. 
    Contract: No automatic stock deduction. Only归零 if mark_depleted=True.
    Transactional.
    """
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 1. Insert Log
        cursor.execute('''
            INSERT INTO production_logs (task_id, roll_id, length, note, operator_id, roll_depleted, status)
            VALUES (?, ?, ?, ?, ?, ?, 'unwashed')
        ''', (task_id, roll_id, length, note, operator_id, 1 if mark_depleted else 0))
        
        # 2. Update Task used_length
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE production_tasks 
            SET used_length = used_length + ?, updated_at = ? 
            WHERE id = ?
        ''', (length, now_str, task_id))

        # 3. Update active Roll length (Deduct printed length)
        # We always deduct the printed length from inventory unless depleted override
        if not mark_depleted:
            cursor.execute('''
                UPDATE rolls
                SET length_m = length_m - ?, updated_at = ?
                WHERE id = ?
            ''', (length, now_str, roll_id))

        # 4. If mark_depleted: Set roll status to 'depleted' and length to 0
        if mark_depleted:
            cursor.execute('''
                UPDATE rolls 
                SET status = 'depleted', length_m = 0, updated_at = ? 
                WHERE id = ?
            ''', (now_str, roll_id))
            
            # Log to roll_history using established service
            fabric_repo.log_roll_history(
                roll_id, 
                'depleted', 
                0, 0, # Qty is not strictly used for simple depletion here but we log 0
                f'production_task:{task_id}',
                f"Depleted via production log (task {task_id})",
                str(operator_id or 'system')
            )

        # 4. Trigger Maintenance
        sync_status_pullback(task_id, cursor)
        
        log_id = cursor.lastrowid
        db.commit()
        return log_id
    except Exception as e:
        db.rollback()
        raise e

def count_unwashed_logs(task_id):
    """Count unwashed logs for a task."""
    result = query_db("SELECT COUNT(*) as c FROM production_logs WHERE task_id = ? AND washed_at IS NULL", (task_id,), one=True)
    return result['c'] if result else 0

def mark_task_done(task_id):
    """Mark task as done. Validates all logs are washed."""
    unwashed = count_unwashed_logs(task_id)
    
    if unwashed > 0:
        raise ValueError("production.error.unwashed_logs_exist")
    
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute('''
            UPDATE production_tasks 
            SET status = 'done', updated_at = ? 
            WHERE id = ?
        ''', (now_str, task_id))
        
        # Trigger maintenance (sync order status)
        sync_status_pullback(task_id, cursor)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e


def manual_adjust_roll(roll_id, new_length, note, operator_id):
    """Manual adjustment of roll length."""
    db = get_db()
    cursor = db.cursor()
    
    try:
        roll = query_db("SELECT * FROM rolls WHERE id = ?", (roll_id,), one=True)
        if not roll:
            raise ValueError("Roll not found")
        
        length_change = new_length - roll['length_m']
        
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE rolls 
            SET length_m = ?, updated_at = ?
            WHERE id = ?
        ''', (new_length, now_str, roll_id))
        
        fabric_repo.log_roll_history(
            roll_id,
            'manual_adjust',
            roll['length_m'],
            new_length,
            'manual_adjust',
            note,
            str(operator_id or 'system')
        )
        
        # Audit Log
        audit_service.log_event(operator_id, 'ADJUST_STOCK', 'rolls', roll_id, f"New Length: {new_length}, Note: {note}")

        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def list_grouped_rolls_for_task(fabric_no, search_query=None):
    """Get available rolls for a fabric (grouped by cylinder)."""
    # Get rolls for this fabric (in_stock only)
    query = '''
        SELECT r.*, c.cylinder_no, c.fabric_id
        FROM rolls r
        LEFT JOIN cylinders c ON r.cylinder_id = c.id
        LEFT JOIN fabrics f ON c.fabric_id = f.id
        WHERE f.fabric_code = ? AND r.status = 'in_stock'
    '''
    params = [fabric_no]
    
    if search_query:
        query += " AND (r.roll_no LIKE ? OR c.cylinder_no LIKE ?)"
        params.extend([f"{search_query}%", f"{search_query}%"])
        
    query += " ORDER BY c.cylinder_no, r.roll_no"
    
    rolls = query_db(query, params)
    
    grouped = {}
    for r in rolls:
        cyl = r['cylinder_no']
        if cyl not in grouped:
            grouped[cyl] = []
        grouped[cyl].append(dict(r))
    return grouped
