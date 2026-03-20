from .db import query_db, execute_db
from . import audit_service
from datetime import datetime

# Constants
ACTION_TEST_USE = 'test_use'
ACTION_DEPLETED = 'depleted'

def list_fabrics_paginated(limit=50, offset=0, q=None):
    if q:
        search = f"%{q}%"
        return query_db('SELECT * FROM fabrics WHERE fabric_code LIKE ? ORDER BY fabric_code LIMIT ? OFFSET ?', (search, limit, offset))
    return query_db('SELECT * FROM fabrics ORDER BY fabric_code LIMIT ? OFFSET ?', (limit, offset))

def list_fabrics(q=None):
    return list_fabrics_paginated(limit=1000, q=q)


def count_fabrics(q=None):
    if q:
        search = f"%{q}%"
        res = query_db('SELECT COUNT(*) as cnt FROM fabrics WHERE fabric_code LIKE ?', (search,), one=True)
    else:
        res = query_db('SELECT COUNT(*) as cnt FROM fabrics', (), one=True)
    return res['cnt'] if res else 0

def get_fabric(id):
    return query_db('SELECT * FROM fabrics WHERE id = ?', (id,), one=True)

def get_fabric_by_code(fabric_code):
    """Get fabric by fabric_code (for duplicate check)"""
    return query_db('SELECT * FROM fabrics WHERE fabric_code = ?', (fabric_code,), one=True)

def create_fabric(fabric_code, width_mm=None, gram_per_yard=None, material_type=None, remark=None):
    """P0: Create fabric with minimal fields"""
    execute_db(
        'INSERT INTO fabrics (fabric_code, width_mm, yard_weight_gyd, material, remark) VALUES (?, ?, ?, ?, ?)',
        (fabric_code, width_mm, gram_per_yard, material_type, remark)
    )
    # Return the newly created fabric
    return get_fabric_by_code(fabric_code)

def list_available_rolls_by_fabric_code(fabric_code):
    """List all in_stock rolls for a given fabric_code, with cylinder info."""
    return query_db('''
        SELECT r.*, c.cylinder_no, f.fabric_code
        FROM rolls r
        JOIN cylinders c ON r.cylinder_id = c.id
        JOIN fabrics f ON c.fabric_id = f.id
        WHERE f.fabric_code = ? AND r.status = 'in_stock'
        ORDER BY c.cylinder_no, r.roll_no
    ''', (fabric_code,))

def update_fabric(id, fabric_code, width_mm=None, gram_per_yard=None, material_type=None, remark=None):
    execute_db(
        'UPDATE fabrics SET fabric_code = ?, width_mm = ?, yard_weight_gyd = ?, material = ?, remark = ? WHERE id = ?',
        (fabric_code, width_mm, gram_per_yard, material_type, remark, id)
    )

def list_cylinders(fabric_id):
    return query_db('SELECT * FROM cylinders WHERE fabric_id = ? ORDER BY cylinder_no', (fabric_id,))

def list_cylinders_with_stats(fabric_id):
    return query_db('''
        SELECT c.*, 
               COUNT(r.id) as roll_count,
               SUM(CASE WHEN r.status = 'in_stock' THEN 1 ELSE 0 END) as in_stock_count,
               SUM(CASE WHEN r.status = 'in_stock' THEN r.length_m ELSE 0 END) as in_stock_sum_length
        FROM cylinders c
        LEFT JOIN rolls r ON c.id = r.cylinder_id
        WHERE c.fabric_id = ?
        GROUP BY c.id
        ORDER BY c.cylinder_no
    ''', (fabric_id,))

def get_cylinder(id):
    return query_db('SELECT c.*, f.fabric_code FROM cylinders c JOIN fabrics f ON c.fabric_id = f.id WHERE c.id = ?', (id,), one=True)

def update_cylinder(id, cylinder_no):
    execute_db(
        'UPDATE cylinders SET cylinder_no = ? WHERE id = ?',
        (cylinder_no, id)
    )

def get_cylinder_stats(cylinder_id):
    return query_db('''
        SELECT 
            COUNT(*) as roll_count,
            SUM(CASE WHEN status = 'in_stock' THEN 1 ELSE 0 END) as in_stock_count,
            SUM(CASE WHEN status = 'depleted' THEN 1 ELSE 0 END) as depleted_count,
            SUM(CASE WHEN status = 'in_stock' THEN length_m ELSE 0 END) as in_stock_sum_length
        FROM rolls
        WHERE cylinder_id = ?
    ''', (cylinder_id,), one=True)

def create_cylinder(fabric_id, cylinder_no):
    return execute_db('INSERT INTO cylinders (fabric_id, cylinder_no) VALUES (?, ?)', (fabric_id, cylinder_no))

def list_rolls_by_cylinder(cylinder_id, status=None):
    query = '''
        SELECT r.*, c.cylinder_no as vat_code,
               (CASE WHEN EXISTS(SELECT 1 FROM production_logs pl WHERE pl.roll_id = r.id) THEN 0 ELSE 1 END) as can_delete
        FROM rolls r 
        JOIN cylinders c ON r.cylinder_id = c.id 
        WHERE r.cylinder_id = ?
    '''
    args = [cylinder_id]
    if status == 'in_stock':
        query += " AND r.status = 'in_stock'"
    elif status == 'depleted':
        query += " AND r.status = 'depleted'"
    
    query += ' ORDER BY r.roll_no'
    return query_db(query, args)

def list_rolls_explorer(fabric_id=None, cylinder_id=None, status=None):
    query = '''
        SELECT r.*, c.cylinder_no, f.fabric_code
        FROM rolls r
        JOIN cylinders c ON r.cylinder_id = c.id
        JOIN fabrics f ON c.fabric_id = f.id
        WHERE 1=1
    '''
    args = []
    if fabric_id:
        query += ' AND f.id = ?'
        args.append(fabric_id)
    if cylinder_id:
        query += ' AND c.id = ?'
        args.append(cylinder_id)
        
    if status == 'in_stock':
        query += " AND r.status = 'in_stock'"
    elif status == 'depleted':
        query += " AND r.status = 'depleted'"
    # if status == 'all' or None, include all rows (no filter)
    
    query += ' ORDER BY r.roll_no ASC'
    return query_db(query, args)

def check_cylinder_has_production(cylinder_id):
    result = query_db('''
        SELECT COUNT(pl.id) as count
        FROM production_logs pl
        JOIN rolls r ON pl.roll_id = r.id
        WHERE r.cylinder_id = ?
    ''', (cylinder_id,), one=True)
    return result['count'] > 0

def delete_cylinder_cascade(cylinder_id):
    # Foreign keys should handle cascading if configured, or we delete manually.
    # Given sqlite default might not be ON DELETE CASCADE, we delete rolls first.
    # But check first!
    if check_cylinder_has_production(cylinder_id):
        raise ValueError("Cannot delete cylinder: Rolls have been used in production.")
        
    # Delete history first (if any) to keep it clean, though ideally history should stay? 
    # User said "Hard delete cylinder + cascade rolls".
    execute_db('DELETE FROM roll_history WHERE roll_id IN (SELECT id FROM rolls WHERE cylinder_id = ?)', (cylinder_id,))
    execute_db('DELETE FROM rolls WHERE cylinder_id = ?', (cylinder_id,))
    execute_db('DELETE FROM cylinders WHERE id = ?', (cylinder_id,))

def delete_fabric_cascade(fabric_code):
    from .db import query_db, execute_db
    fabric = get_fabric_by_code(fabric_code)
    if not fabric:
        raise ValueError(f"Fabric code {fabric_code} not found")
        
    result = query_db('''
        SELECT COUNT(pl.id) as count
        FROM production_logs pl
        JOIN rolls r ON pl.roll_id = r.id
        JOIN cylinders c ON r.cylinder_id = c.id
        WHERE c.fabric_id = ?
    ''', (fabric['id'],), one=True)
    if result['count'] > 0:
        raise ValueError("Cannot delete fabric: Rolls have been used in production.")
        
    execute_db('''
        DELETE FROM roll_history WHERE roll_id IN (
            SELECT r.id FROM rolls r
            JOIN cylinders c ON r.cylinder_id = c.id
            WHERE c.fabric_id = ?
        )
    ''', (fabric['id'],))
    execute_db('DELETE FROM rolls WHERE cylinder_id IN (SELECT id FROM cylinders WHERE fabric_id = ?)', (fabric['id'],))
    execute_db('DELETE FROM cylinders WHERE fabric_id = ?', (fabric['id'],))
    execute_db('DELETE FROM fabrics WHERE id = ?', (fabric['id'],))

def search_in_stock_rolls(query=None):
    from .db import query_db
    sql = '''
        SELECT r.*, c.cylinder_no, f.fabric_code as fabric_no
        FROM rolls r
        JOIN cylinders c ON r.cylinder_id = c.id
        JOIN fabrics f ON c.fabric_id = f.id
        WHERE r.status = 'in_stock'
    '''
    params = ()
    if query:
        sql += ' AND (r.roll_no LIKE ? OR f.fabric_code LIKE ?)'
        params = (f'%{query}%', f'%{query}%')
    
    sql += ' ORDER BY r.created_at DESC LIMIT 100'
    return query_db(sql, params)

def check_roll_has_production(roll_id):
    result = query_db('SELECT COUNT(*) as count FROM production_logs WHERE roll_id = ?', (roll_id,), one=True)
    return result['count'] > 0

def delete_roll_safe(roll_id):
    if check_roll_has_production(roll_id):
        raise ValueError("Cannot delete roll: Has been used in production.")
    
    execute_db('DELETE FROM roll_history WHERE roll_id = ?', (roll_id,))
    execute_db('DELETE FROM rolls WHERE id = ?', (roll_id,))

def create_stock_in_batch(fabric_id, cylinder_no, roll_rows, user_name='operator'):
    # 1. Resolve Cylinder
    cylinder = query_db('SELECT id FROM cylinders WHERE fabric_id = ? AND cylinder_no = ?', (fabric_id, cylinder_no), one=True)
    if cylinder:
        cylinder_id = cylinder['id']
    else:
        # Create new cylinder
        execute_db('INSERT INTO cylinders (fabric_id, cylinder_no) VALUES (?, ?)', (fabric_id, cylinder_no))
        # Get ID back
        # In sqlite execute_db usually returns rowcount or cursor. We might need lastrowid.
        # Our db wrapper execute_db returns 'cursor'.
        cur = execute_db('SELECT last_insert_rowid()')
        # cursor is returned by execute_db in implementation? No, execute_db returns result of cursor.execute (cursor object).
        # Wait, the implementation of execute_db in db.py:
        # def execute_db(query, args=()):
        #     db = get_db()
        #     cur = db.execute(query, args)
        #     db.commit()
        #     return cur
        # So yes, cur.lastrowid works.
        
        # But wait, to be safe I'll just query it back or use a dedicated method if I had one.
        # I'll rely on query back for safety.
        cylinder_created = query_db('SELECT id FROM cylinders WHERE fabric_id = ? AND cylinder_no = ?', (fabric_id, cylinder_no), one=True)
        cylinder_id = cylinder_created['id']

    # 2. Insert Rolls
    # rows: list of dict {roll_no, length_m, remark (optional)}
    for row in roll_rows:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        roll_id = execute_db(
            'INSERT INTO rolls (cylinder_id, roll_no, length_m, remark, status, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
            (cylinder_id, row['roll_no'], row['length_m'], row.get('remark') or None, 'in_stock', now_str)
        )
        log_roll_history(
            roll_id, 
            'stock_in', 
            0, 
            row['length_m'], 
            'stock_in_batch', 
            'Stock-in', 
            user_name
        )

def get_roll(id):
    roll = query_db('SELECT r.*, c.cylinder_no, f.fabric_code, f.id as fabric_id, c.id as cylinder_id FROM rolls r JOIN cylinders c ON r.cylinder_id = c.id JOIN fabrics f ON c.fabric_id = f.id WHERE r.id = ?', (id,), one=True)
    return roll

def create_roll(cylinder_id, roll_no, length_m, weight_kg, remark, user_name='operator'):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    roll_id = execute_db(
        'INSERT INTO rolls (cylinder_id, roll_no, length_m, weight_kg, remark, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
        (cylinder_id, roll_no, length_m, weight_kg, remark, now_str)
    )
    log_roll_history(
        roll_id, 
        'stock_in', 
        0, 
        length_m, 
        'create_roll', 
        'Stock-in', 
        user_name
    )
    return roll_id

def log_roll_history(roll_id, action, old_qty, new_qty, source, note, created_by):
    delta = new_qty - old_qty
    execute_db(
        '''INSERT INTO roll_history 
           (roll_id, action, old_qty, new_qty, delta, source, note, created_by) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (roll_id, action, old_qty, new_qty, delta, source, note, created_by)
    )

def adjust_roll_stock(roll_id, new_length, source='manual_adjust', note='', user_name='operator'):
    roll = get_roll(roll_id)
    if not roll:
        raise ValueError("Roll not found")
    old_length = roll['length_m']
    
    # Simple status logic: 0 -> depleted, >0 -> in_stock
    status = 'depleted' if new_length == 0 else 'in_stock'
    
    # Update roll
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    execute_db('UPDATE rolls SET length_m = ?, status = ?, updated_at = ? WHERE id = ?', 
               (new_length, status, now_str, roll_id))
    
    # Log history
    log_roll_history(roll_id, 'manual_adjust', old_length, new_length, source, note, user_name)

    # Audit Log
    from . import production_repo
    # Get user_id if possible
    from flask import g
    op_id = g.user['id'] if g and hasattr(g, 'user') and g.user else 0
    audit_service.log_event(op_id, 'ADJUST_STOCK', 'rolls', roll_id, f"New Length: {new_length}, Note: {note}")

def deplete_roll(roll_id, source, note, user_name):
    roll = get_roll(roll_id)
    old_length = roll['length_m']
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    execute_db("UPDATE rolls SET length_m = 0, status = 'depleted', updated_at = ? WHERE id = ?", (now_str, roll_id))
    
    log_roll_history(roll_id, 'depleted', old_length, 0, source, note, user_name)
def record_test_consume(roll_id, used_m, note, task_id, depleted=False, user_name='operator'):
    # Fetch all metadata in one query for traceability
    meta = query_db('''
        SELECT 
            r.roll_no, 
            c.cylinder_no, 
            f.fabric_code,
            pt.id as task_id,
            pt.sample_id,
            o.order_no,
            s.sample_no,
            s.title as sample_title,
            r.length_m as old_length
        FROM rolls r
        JOIN cylinders c ON r.cylinder_id = c.id
        JOIN fabrics f ON c.fabric_id = f.id
        LEFT JOIN production_tasks pt ON pt.id = ?
        LEFT JOIN orders o ON pt.order_id = o.id
        LEFT JOIN samples s ON pt.sample_id = s.id
        WHERE r.id = ?
    ''', (task_id, roll_id), one=True)

    if not meta:
        raise ValueError("Roll not found")

    old_length = meta['old_length']
    is_clamped = False
    new_length = old_length - used_m
    
    if new_length < 0:
        new_length = 0
        is_clamped = True
        
    if depleted:
        new_length = 0
        
    status = 'depleted' if new_length == 0 else 'in_stock'
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    execute_db('UPDATE rolls SET length_m = ?, status = ?, updated_at = ? WHERE id = ?', 
               (new_length, status, now_str, roll_id))
    
    # Construct Sample Label: {sample_no} - {title} > {title} > S{id}
    sample_label = "-"
    if meta['sample_no'] and meta['sample_title']:
        sample_label = f"{meta['sample_no']} - {meta['sample_title']}"
    elif meta['sample_title']:
        sample_label = meta['sample_title']
    elif meta['sample_id']:
        sample_label = f"S{meta['sample_id']}"

    # Construct Rich Note
    # TEST_CONSUME | Order={order_no} | Task={task_id} | Fabric={fabric_code} | Vat={cylinder_no} | Roll={roll_no} | Sample={sample_label} | Note={user_note}
    rich_note = (
        f"TEST_CONSUME | "
        f"Order={meta['order_no'] or '-'} | "
        f"Task={task_id or '-'} | "
        f"Fabric={meta['fabric_code'] or '-'} | "
        f"Vat={meta['cylinder_no'] or '-'} | "
        f"Roll={meta['roll_no'] or '-'} | "
        f"Sample={sample_label} | "
        f"Note={note or '-'}"
    )
    
    if is_clamped:
        rich_note += " (OVER-CONSUMED/CLAMPED)"

    # Log roll history
    log_roll_history(
        roll_id, 
        ACTION_TEST_USE, 
        old_length, 
        new_length, 
        f'production_task:{task_id}', 
        rich_note, 
        user_name
    )

def list_roll_history(roll_id, limit=50):
    return query_db('SELECT * FROM roll_history WHERE roll_id = ? ORDER BY created_at DESC LIMIT ?', (roll_id, limit))

def list_cylinder_history(cylinder_id, limit=100):
     return query_db('''
        SELECT h.*, r.roll_no 
        FROM roll_history h 
        JOIN rolls r ON h.roll_id = r.id 
        WHERE r.cylinder_id = ? 
        ORDER BY h.created_at DESC 
        LIMIT ?
    ''', (cylinder_id, limit))

def find_first_fabric_with_cylinder_prefix(prefix):
    return query_db('''
        SELECT f.id 
        FROM fabrics f 
        JOIN cylinders c ON f.id = c.fabric_id 
        WHERE c.cylinder_no LIKE ? || '%' 
        ORDER BY f.fabric_code 
        LIMIT 1
    ''', (prefix,), one=True)

def apply_test_consume(roll_id, consumed_length_m, mark_empty, note, actor):
    """
    Apply test consume logic (no task required).
    Updates roll length/status and logs to roll_history.
    """
    from .db import commit
    roll = get_roll(roll_id)
    if not roll:
        raise ValueError("Roll not found")
        
    old_length = roll['length_m']
    
    
    # 1. Apply Consumption (Test Use)
    intermediate_length = max(0, old_length - consumed_length_m)
    status_after_consume = 'depleted' if intermediate_length == 0 else 'in_stock'
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    execute_db('UPDATE rolls SET length_m = ?, status = ?, updated_at = ? WHERE id = ?', 
               (intermediate_length, status_after_consume, now_str, roll_id))
               
    log_roll_history(
        roll_id,
        ACTION_TEST_USE,
        old_length,
        intermediate_length,
        'test_consume',
        note,
        actor
    )

    # 2. Mark Empty (Depleted) if explicitly requested and implies extra reduction
    if mark_empty and intermediate_length > 0:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        execute_db("UPDATE rolls SET length_m = 0, status = 'depleted', updated_at = ? WHERE id = ?", (now_str, roll_id))
        log_roll_history(
            roll_id,
            ACTION_DEPLETED,
            intermediate_length,
            0,
            'test_consume',
            'Marked empty after test consume',
            actor
        )
    # Audit Log
    from flask import g
    op_id = g.user['id'] if g and hasattr(g, 'user') and g.user else 0
    audit_service.log_event(op_id, 'TEST_CONSUME', 'rolls', roll_id, f"Consumed: {consumed_length_m}, Empty: {mark_empty}, Note: {note}")

    commit()
    return get_roll(roll_id)

def deplete_roll(roll_id, actor='operator'):
    return apply_test_consume(roll_id, 0, True, 'Marked depleted', actor)
