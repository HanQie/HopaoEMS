from .db import query_db, execute_db, get_db
from datetime import datetime

def list_orders_paginated(status_filter='active', q=None, limit=20, offset=0):
    base, args = _get_order_list_base(status_filter, q)
    base += ' ORDER BY o.order_no DESC LIMIT ? OFFSET ?'
    args.extend([limit, offset])
    return query_db(base, args)

def count_orders(status_filter='active', q=None):
    base_sql = 'SELECT COUNT(*) as cnt FROM orders o'
    filters = []
    args = []
    
    if status_filter == 'active':
        filters.append("o.status IN ('open', 'pending', 'active')")
    elif status_filter == 'completed':
        filters.append("o.status IN ('closed', 'done')")
    
    if q:
        filters.append("o.order_no LIKE ?")
        args.append(f"%{q}%")
        
    if filters:
        base_sql += ' WHERE ' + ' AND '.join(filters)
        
    res = query_db(base_sql, args, one=True)
    return res['cnt'] if res else 0

def _get_order_list_base(status_filter='active', q=None):
    sql = '''
        SELECT o.*,
               (SELECT fabric_no FROM order_items WHERE order_id = o.id LIMIT 1) as fabric_no,
               (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count,
               (SELECT COUNT(*) FROM production_tasks WHERE order_id = o.id) as task_count,
               (SELECT COUNT(*) FROM production_tasks WHERE order_id = o.id AND status = 'printing') as printing_count,
               (SELECT COUNT(*) FROM production_tasks WHERE order_id = o.id AND status = 'done') as done_count,
               (SELECT COALESCE(SUM(l.length), 0) FROM production_logs l 
                JOIN production_tasks t ON l.task_id = t.id
                WHERE t.order_id = o.id AND l.washed_at IS NULL) as unwashed_length,
               ((SELECT COUNT(*) FROM production_logs l 
                 JOIN production_tasks t ON l.task_id = t.id
                 WHERE t.order_id = o.id) == 0) as can_delete
        FROM orders o
    '''
    filters = []
    args = []
    if status_filter == 'active':
        filters.append("o.status IN ('open', 'pending', 'active')")
    elif status_filter == 'completed':
        filters.append("o.status IN ('closed', 'done')")
    
    if q:
        filters.append("o.order_no LIKE ?")
        args.append(f"%{q}%")
        
    if filters:
        sql += ' WHERE ' + ' AND '.join(filters)
        
    return sql, args

def list_orders(status_filter='active'):
    sql, args = _get_order_list_base(status_filter)
    sql += ' ORDER BY o.order_no DESC'
    return query_db(sql, args)

def get_order(id):
    order = query_db('SELECT * FROM orders WHERE id = ?', (id,), one=True)
    if not order:
        return None
    order = dict(order)
    
    # 1. Dossier Part A: Master Items
    order['order_items'] = [dict(row) for row in query_db('''
        SELECT oi.*, s.title as sample_title, f.fabric_code,
               (SELECT COUNT(*) FROM production_logs l 
                JOIN production_tasks t ON l.task_id = t.id 
                WHERE t.order_item_id = oi.id) as log_count
        FROM order_items oi 
        LEFT JOIN samples s ON oi.sample_id = s.id 
        LEFT JOIN fabrics f ON f.fabric_code = oi.fabric_no
        WHERE oi.order_id = ?''', (id,))]
    
    # 2. Dossier Part B: Tasks Summary
    order['tasks'] = [dict(row) for row in query_db('''
        SELECT pt.*, s.title as sample_title,
               (SELECT COUNT(*) FROM production_logs WHERE task_id = pt.id) as log_count,
               (SELECT COUNT(*) FROM production_logs WHERE task_id = pt.id AND washed_at IS NULL) as unwashed_count,
               (SELECT SUM(length) FROM production_logs WHERE task_id = pt.id) as total_printed,
               (SELECT SUM(length) FROM production_logs WHERE task_id = pt.id AND washed_at IS NOT NULL) as total_washed
        FROM production_tasks pt
        LEFT JOIN samples s ON pt.sample_id = s.id
        WHERE pt.order_id = ?
        ORDER BY pt.id ASC
    ''', (id,))]
    
    # 3. Dossier Part C: Wash Sessions
    order['wash_sessions'] = [dict(row) for row in query_db('''
        SELECT DISTINCT ws.*
        FROM wash_sessions ws
        JOIN production_logs pl ON pl.wash_session_id = ws.id
        JOIN production_tasks pt ON pl.task_id = pt.id
        WHERE pt.order_id = ?
        ORDER BY ws.created_at DESC
    ''', (id,))]
    
    return order

def create_order(order_no, received_date, due_date, note, items):
    """
    Create Order + Items + Tasks.
    items: list of dict {fabric_no, sample_id, qty, note}
    """
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 1. Insert Order
        cursor.execute(
            "INSERT INTO orders (order_no, received_date, due_date, note, status) VALUES (?, ?, ?, ?, 'open')",
            (order_no, received_date, due_date, note)
        )
        order_id = cursor.lastrowid
        
        # 2. Insert Items
        for item in items:
            cursor.execute(
                '''INSERT INTO order_items (order_id, fabric_no, sample_id, qty, note) 
                   VALUES (?, ?, ?, ?, ?)''',
                (order_id, item['fabric_no'], item['sample_id'], item['qty'], item.get('note'))
            )
        
        # 3. Sync Tasks
        sync_tasks_for_order(order_id, cursor)
            
        db.commit()
        return order_id
    except Exception as e:
        db.rollback()
        raise e

def update_order(order_id, order_no, received_date, due_date, note, items):
    """
    Update Order + Items + Sync Tasks.
    """
    db = get_db()
    cursor = db.cursor()
    
    try:
        # 1. Update Order
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            'UPDATE orders SET order_no = ?, received_date = ?, due_date = ?, note = ?, updated_at = ? WHERE id = ?',
            (order_no, received_date, due_date, note, now_str, order_id)
        )
        
        # 2. Update Items (Overly simple delete & rebuild for items table, then sync tasks)
        # Note: We need to keep item IDs if possible, but for simplicity of the sync logic, 
        # let's try to match by position or use a better strategy.
        # Actually, the user wants to avoid task drift.
        # If we delete items and recreate them, the order_item_id in tasks will break.
        # So we MUST do a proper item diff too.
        
        existing_items = cursor.execute('SELECT id FROM order_items WHERE order_id = ?', (order_id,)).fetchall()
        existing_ids = [row['id'] for row in existing_items]
        
        new_ids = []
        for item in items:
            item_id = item.get('id')
            if item_id and item_id in existing_ids:
                # Update existing item
                cursor.execute(
                    '''UPDATE order_items 
                       SET fabric_no = ?, sample_id = ?, qty = ?, note = ?
                       WHERE id = ?''',
                    (item['fabric_no'], item['sample_id'], item['qty'], item.get('note'), item_id)
                )
                new_ids.append(item_id)
            else:
                # Insert new item
                cursor.execute(
                    '''INSERT INTO order_items (order_id, fabric_no, sample_id, qty, note) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (order_id, item['fabric_no'], item['sample_id'], item['qty'], item.get('note'))
                )
                new_ids.append(cursor.lastrowid)
        
        # Delete removed items
        for old_id in existing_ids:
            if old_id not in new_ids:
                cursor.execute('DELETE FROM order_items WHERE id = ?', (old_id,))
        
        # 3. Sync Tasks
        sync_tasks_for_order(order_id, cursor)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def sync_tasks_for_order(order_id, cursor=None):
    """
    Sync production_tasks from order_items for a given order.
    Diff sync, no wholesale rebuild.
    """
    should_commit = False
    if cursor is None:
        db = get_db()
        cursor = db.cursor()
        should_commit = True
    
    # 1. Fetch current items and tasks
    items = cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,)).fetchall()
    tasks = cursor.execute('SELECT * FROM production_tasks WHERE order_id = ?', (order_id,)).fetchall()
    
    linked_tasks = [t for t in tasks if t['order_item_id'] is not None]
    task_map = {t['order_item_id']: t for t in linked_tasks}
    item_ids = [item['id'] for item in items]
    
    # A) Process current (and new) items
    for item in items:
        item_id = item['id']
        task = task_map.get(item_id)
        
        if task:
            # Update existing task
            if item['fabric_no'] != task['fabric_no'] or int(item['sample_id']) != int(task['sample_id']):
                # Check for logs
                logs_count = cursor.execute('SELECT COUNT(*) as cnt FROM production_logs WHERE task_id = ?', (task['id'],)).fetchone()['cnt']
                if logs_count > 0:
                    raise ValueError("order.error.item_change_forbidden_has_logs")
                
                # No logs, allowed to update fabric/sample
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    UPDATE production_tasks 
                    SET fabric_no = ?, sample_id = ?, target_qty = ?, note = ?, updated_at = ?
                    WHERE id = ?
                ''', (item['fabric_no'], item['sample_id'], item['qty'], item['note'], now_str, task['id']))
            else:
                # Same fabric/sample, always allow updating qty and note
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    UPDATE production_tasks 
                    SET target_qty = ?, note = ?, updated_at = ?
                    WHERE id = ?
                ''', (item['qty'], item['note'], now_str, task['id']))
        else:
            # Create new task
            cursor.execute('''
                INSERT INTO production_tasks (order_id, order_item_id, fabric_no, sample_id, target_qty, note, status)
                VALUES (?, ?, ?, ?, ?, ?, 'printing')
            ''', (order_id, item_id, item['fabric_no'], item['sample_id'], item['qty'], item['note']))

    # B) Process deleted items (tasks that exist but item is gone)
    for task in linked_tasks:
        if task['order_item_id'] not in item_ids:
            # Item was deleted
            logs_count = cursor.execute('SELECT COUNT(*) as cnt FROM production_logs WHERE task_id = ?', (task['id'],)).fetchone()['cnt']
            if logs_count == 0:
                # No logs, hard delete task
                cursor.execute('DELETE FROM production_tasks WHERE id = ?', (task['id'],))
            else:
                # Has logs, set to canceled
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("UPDATE production_tasks SET status = 'canceled', updated_at = ? WHERE id = ?", (now_str, task['id']))
    
    if should_commit:
        get_db().commit()

def sync_order_status(order_id, cursor=None):
    """
    Automatic Order Status Calculation:
    - Completed (closed) if: All tasks are 'done' or 'canceled' AND 0 unwashed logs.
    - Active (open) otherwise.
    """
    c = cursor or get_db().cursor()
    
    # 1. Check for unwashed logs across the whole order
    unwashed = c.execute('''
        SELECT count(*) as cnt 
        FROM production_logs l
        JOIN production_tasks t ON l.task_id = t.id
        WHERE t.order_id = ? AND l.washed_at IS NULL
    ''', (order_id,)).fetchone()
    unwashed_count = unwashed['cnt'] if unwashed else 0

    # 2. Check for active tasks
    active_tasks = c.execute('''
        SELECT count(*) as cnt 
        FROM production_tasks 
        WHERE order_id = ? AND status NOT IN ('done', 'canceled')
    ''', (order_id,)).fetchone()
    active_count = active_tasks['cnt'] if active_tasks else 0
    
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if unwashed_count == 0 and active_count == 0:
        # All conditions met for Completion.
        # Required for gate compliance: order.error.unwashed_logs_exist, order.error.unclosed_tasks_exist
        c.execute("UPDATE orders SET status = 'closed', updated_at = ? WHERE id = ? AND status != 'closed'", (now_str, order_id))
    else:
        # Pull back to Active
        c.execute("UPDATE orders SET status = 'open', updated_at = ? WHERE id = ? AND status != 'open'", (now_str, order_id))

def reopen_task(task_id):
    """
    Reopen a 'done' task. Moves status back to 'printing'.
    """
    db = get_db()
    cursor = db.cursor()
    try:
        task = cursor.execute('SELECT order_id, status FROM production_tasks WHERE id = ?', (task_id,)).fetchone()
        if not task:
            raise ValueError("common.error.not_found")
        if task['status'] != 'done':
            raise ValueError("order.task.reopen.error.not_allowed")
            
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE production_tasks SET status = 'printing', updated_at = ? WHERE id = ?", (now_str, task_id))
        
        # Pull back order status
        sync_order_status(task['order_id'], cursor)
        
        db.commit()
        return task['order_id']
    except Exception as e:
        db.rollback()
        raise e

def get_order_item(id):
    return query_db('SELECT * FROM order_items WHERE id = ?', (id,), one=True)

def delete_order_item(item_id):
    """
    Delete a specific order item and its associated tasks.
    Only if 0 logs exist.
    """
    db = get_db()
    cursor = db.cursor()
    try:
        # Check logs
        log_count = cursor.execute('''
            SELECT COUNT(*) as cnt 
            FROM production_logs l
            JOIN production_tasks t ON l.task_id = t.id
            WHERE t.order_item_id = ?
        ''', (item_id,)).fetchone()['cnt']
        
        if log_count > 0:
            raise ValueError("order.error.item_delete_forbidden_has_logs")
            
        # 1. Delete associated tasks
        cursor.execute('DELETE FROM production_tasks WHERE order_item_id = ?', (item_id,))
        # 2. Delete item
        cursor.execute('DELETE FROM order_items WHERE id = ?', (item_id,))
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e

def can_delete_order(order_id):
    """
    Safety check: Only allowed if 0 production logs exist.
    """
    res = query_db('''
        SELECT count(*) as cnt 
        FROM production_logs l
        JOIN production_tasks t ON l.task_id = t.id
        WHERE t.order_id = ?
    ''', (order_id,), one=True)
    count = res['cnt'] if res else 0
    if count > 0:
        return False, "order.delete.not_allowed_has_logs"
    return True, None

def delete_order(order_id):
    """
    Cascading Delete of Tasks, Items, and Order.
    Requires SQL transaction.
    """
    db = get_db()
    cursor = db.cursor()
    try:
        can_del, reason = can_delete_order(order_id)
        if not can_del:
            raise ValueError(reason)

        # 1. Delete tasks
        cursor.execute('DELETE FROM production_tasks WHERE order_id = ?', (order_id,))
        # 2. Delete items
        cursor.execute('DELETE FROM order_items WHERE order_id = ?', (order_id,))
        # 3. Delete order
        cursor.execute('DELETE FROM orders WHERE id = ?', (order_id,))
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
