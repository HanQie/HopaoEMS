from .db import query_db, execute_db

def normalize_preview_path(path):
    """Ensure preview path is a relative key and contains no dangerous characters."""
    if not path:
        return None
    # Block colon, backslash, leading slash, same-level traversal
    if ":" in path or "\\" in path or path.startswith("/") or ".." in path:
        raise ValueError("sample.error.invalid_path_key")
    return path

def list_samples_paginated(q=None, limit=50, offset=0):
    if q:
        search = f"%{q}%"
        return query_db('SELECT * FROM samples WHERE title LIKE ? OR sample_no LIKE ? ORDER BY sample_no DESC LIMIT ? OFFSET ?', (search, search, limit, offset))
    return query_db('SELECT * FROM samples ORDER BY sample_no DESC LIMIT ? OFFSET ?', (limit, offset))

def list_samples_paginated_enriched(q=None, limit=50, offset=0):
    """Paginated samples with correction_count, task_count, last_activity in a single query."""
    base = '''
        SELECT s.*,
            COUNT(DISTINCT scm.id) AS correction_count,
            COUNT(DISTINCT pt.id)  AS task_count
        FROM samples s
        LEFT JOIN sample_color_map scm ON scm.sample_id = s.id
        LEFT JOIN production_tasks pt  ON pt.sample_id  = s.id
    '''
    if q:
        search = f"%{q}%"
        sql = base + ' WHERE (s.title LIKE ? OR s.sample_no LIKE ?) GROUP BY s.id ORDER BY s.sample_no DESC LIMIT ? OFFSET ?'
        return query_db(sql, (search, search, limit, offset))
    sql = base + ' GROUP BY s.id ORDER BY s.sample_no DESC LIMIT ? OFFSET ?'
    return query_db(sql, (limit, offset))

def count_samples(q=None):
    if q:
        search = f"%{q}%"
        res = query_db('SELECT COUNT(*) as cnt FROM samples WHERE title LIKE ? OR sample_no LIKE ?', (search, search), one=True)
    else:
        res = query_db('SELECT COUNT(*) as cnt FROM samples', (), one=True)
    return res['cnt'] if res else 0

def list_samples(q=None):
    return list_samples_paginated(q, limit=200 if q else 80, offset=0)

def get_sample(id):
    # Try direct lookup (usually int)
    res = query_db('SELECT * FROM samples WHERE id = ?', (id,), one=True)
    if res:
        return res
        
    # Fallback: Try string lookup (if id was passed as int but stored as string, or vice versa)
    return query_db('SELECT * FROM samples WHERE id = ?', (str(id),), one=True)

def _ensure_schema():
    try:
        execute_db('ALTER TABLE samples ADD COLUMN sampled_date TEXT')
    except Exception:
        pass

def create_sample(sample_no, title, fabric_no, sales_code=None, version=None,
                 date_received=None, sampled_date=None, source_filename=None, source_mime=None, 
                 source_path=None, preview_path=None, preview_mime=None, 
                 preview_size=None, remark=None, printing_environment=None, printing_file_name=None):
    _ensure_schema()
    preview_path = normalize_preview_path(preview_path)
    return execute_db(
        '''INSERT INTO samples (
            sample_no, title, fabric_no, sales_code, version,
            date_received, sampled_date, source_filename, source_mime, source_path,
            preview_path, preview_mime, preview_size, remark,
            printing_environment, printing_file_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (sample_no, title, fabric_no, sales_code, version,
         date_received, sampled_date, source_filename, source_mime, source_path,
         preview_path, preview_mime, preview_size, remark,
         printing_environment, printing_file_name)
    )

def update_sample(id, title=None, fabric_no=None, date_received=None, sampled_date=None, 
                  version=None, printing_environment=None, printing_file_name=None, 
                  remark=None, preview_path=None):
    _ensure_schema()
    # Only updates editable fields
    return execute_db(
        '''UPDATE samples SET 
            title = COALESCE(?, title),
            fabric_no = COALESCE(?, fabric_no),
            date_received = COALESCE(?, date_received),
            sampled_date = COALESCE(?, sampled_date),
            version = COALESCE(?, version),
            printing_environment = COALESCE(?, printing_environment),
            printing_file_name = COALESCE(?, printing_file_name),
            remark = COALESCE(?, remark),
            preview_path = COALESCE(?, preview_path)
           WHERE id = ?''',
        (title, fabric_no, date_received, sampled_date, version, printing_environment, printing_file_name, remark, preview_path, id)
    )

def list_color_maps(sample_id):
    return query_db('SELECT * FROM sample_color_map WHERE sample_id = ? ORDER BY created_at', (sample_id,))

def add_color_map(sample_id, pick_x, pick_y, rgb_r, rgb_g, rgb_b, hex_val, note):
    return execute_db(
        '''INSERT INTO sample_color_map (
            sample_id, pick_x, pick_y, rgb_r, rgb_g, rgb_b, hex, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (sample_id, pick_x, pick_y, rgb_r, rgb_g, rgb_b, hex_val, note)
    )

def add_full_color_correction(sample_id, rgb_r, rgb_g, rgb_b, target_mode, 
                               target_l=None, target_a=None, target_b=None, target_note=None,
                               pick_x=None, pick_y=None, hex_val=None):
    if hex_val is None and rgb_r is not None and rgb_g is not None and rgb_b is not None:
        hex_val = '#%02x%02x%02x' % (int(rgb_r), int(rgb_g), int(rgb_b))
    return execute_db(
        '''INSERT INTO sample_color_map (
            sample_id, rgb_r, rgb_g, rgb_b, target_mode, 
            target_l, target_a, target_b, target_note,
            pick_x, pick_y, hex
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (sample_id, rgb_r, rgb_g, rgb_b, target_mode, 
         target_l, target_a, target_b, target_note,
         pick_x, pick_y, hex_val)
    )

def pick_pixel_color(preview_path, x, y):
    """
    Read pixel from image file and return (r, g, b) and hex.
    """
    import os
    from PIL import Image
    from flask import current_app
    
    upload_dir = current_app.config['SAMPLES_UPLOAD_DIR']
    file_path = os.path.join(upload_dir, preview_path)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError("sample.pick_color.error.no_preview")
        
    with Image.open(file_path) as img:
        # Canonicalize to RGB
        rgb_img = img.convert('RGB')
        width, height = rgb_img.size
        
        if x < 0 or x >= width or y < 0 or y >= height:
            raise ValueError("sample.pick_color.error.out_of_bounds")
            
        r, g, b = rgb_img.getpixel((x, y))
        hex_val = '#{:02X}{:02X}{:02X}'.format(r, g, b)
        return (r, g, b), hex_val

def check_sample_in_use(id):
    """
    Check if sample is used in orders or production tasks.
    Returns boolean.
    """
    # Check Order Items
    res = query_db('SELECT id FROM order_items WHERE sample_id = ? LIMIT 1', (id,), one=True)
    if res:
        return True
    
    # Check Production Tasks
    res = query_db('SELECT id FROM production_tasks WHERE sample_id = ? LIMIT 1', (id,), one=True)
    if res:
        return True
        
    return False

def delete_sample_safe(id):
    """
    Delete sample and related data if not in use.
    Raises ValueError if in use.
    """
    if check_sample_in_use(id):
        raise ValueError("sample.error.in_use")
        
    # Cascade delete logs (color map)
    execute_db('DELETE FROM sample_color_map WHERE sample_id = ?', (id,))
    
    # Delete sample
    # Note: We do NOT delete the physical file to avoid issues with shared files or historical integrity.
    # The file remains in uploads/samples.
    execute_db('DELETE FROM samples WHERE id = ?', (id,))

# Alias for compatibility if needed, but safe version is preferred
delete_sample = delete_sample_safe

def clear_color_corrections(sample_id):
    return execute_db('DELETE FROM sample_color_map WHERE sample_id = ?', (sample_id,))

def replace_color_corrections(sample_id, rows):
    """
    Clear all corrections for a sample and replace with new rows.
    rows: list of dicts with {rgb_r, rgb_g, rgb_b, target_mode, target_l, target_a, target_b, target_note}
    """
    # Note: execute_db currently doesn't support manual Transaction blocks easily with the current wrapper
    # but since it's a single SQLite connection per request, it's relatively safe.
    # To be strictly atomic, we'd need a different pattern, but we'll follow existing execute_db usage.
    clear_color_corrections(sample_id)
    for row in rows:
        add_full_color_correction(
            sample_id,
            rgb_r=row.get('rgb_r'),
            rgb_g=row.get('rgb_g'),
            rgb_b=row.get('rgb_b'),
            target_mode=row.get('target_mode'),
            target_l=row.get('target_l'),
            target_a=row.get('target_a'),
            target_b=row.get('target_b'),
            target_note=row.get('target_note')
        )

