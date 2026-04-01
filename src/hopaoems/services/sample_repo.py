import difflib
import re

from .db import query_db, execute_db


_SAMPLE_SEARCH_VARIANTS = str.maketrans({
    "籃": "藍",
    "臺": "台",
})

def normalize_preview_path(path):
    """Ensure preview path is a relative key and contains no dangerous characters."""
    if not path:
        return None
    # Block colon, backslash, leading slash, same-level traversal
    if ":" in path or "\\" in path or path.startswith("/") or ".." in path:
        raise ValueError("sample.error.invalid_path_key")
    return path


def _normalize_sample_query(text):
    if not text:
        return ""
    normalized = str(text).strip().lower().translate(_SAMPLE_SEARCH_VARIANTS)
    normalized = re.sub(r"[\s_\-()（）\[\]{}]+", "", normalized)
    return normalized


def _score_sample_match(query, sample_no, title):
    raw_query = (query or "").strip()
    if not raw_query:
        return 0.0

    sample_no = sample_no or ""
    title = title or ""
    norm_query = _normalize_sample_query(raw_query)
    norm_no = _normalize_sample_query(sample_no)
    norm_title = _normalize_sample_query(title)

    if raw_query == sample_no or raw_query == title:
        return 1.0
    if norm_query and (norm_query == norm_no or norm_query == norm_title):
        return 0.99

    score = 0.0
    if raw_query and (raw_query in sample_no or raw_query in title):
        score = max(score, 0.95)
    if norm_query and ((norm_query in norm_no) or (norm_query in norm_title)):
        score = max(score, 0.93)

    if norm_query and norm_title:
        score = max(score, difflib.SequenceMatcher(None, norm_query, norm_title).ratio())
    if norm_query and norm_no:
        score = max(score, difflib.SequenceMatcher(None, norm_query, norm_no).ratio())

    if norm_query:
        title_overlap = len(set(norm_query) & set(norm_title)) / max(len(set(norm_query)), 1)
        no_overlap = len(set(norm_query) & set(norm_no)) / max(len(set(norm_query)), 1)
        score = max(score, title_overlap * 0.82, no_overlap * 0.8)

    return round(min(score, 1.0), 4)


def find_sample_candidates(query, limit=5, min_score=0.45):
    rows = query_db(
        'SELECT id, sample_no, title, fabric_no, preview_path FROM samples',
        (),
        one=False,
    ) or []
    scored = []
    for row in rows:
        sample_no = row["sample_no"] if "sample_no" in row.keys() else ""
        title = row["title"] if "title" in row.keys() else ""
        fabric_no = row["fabric_no"] if "fabric_no" in row.keys() else ""
        preview_path = row["preview_path"] if "preview_path" in row.keys() else ""
        score = _score_sample_match(query, sample_no, title)
        if score >= min_score:
            scored.append({
                "id": row["id"],
                "sample_no": sample_no,
                "title": title,
                "fabric_no": fabric_no,
                "preview_path": preview_path,
                "score": score,
            })

    scored.sort(key=lambda item: (item["score"], item["sample_no"] or ""), reverse=True)
    return scored[:limit]


def resolve_sample_for_ai(query, min_score=0.45):
    candidates = find_sample_candidates(query, limit=5, min_score=min_score)
    if not candidates:
        raise ValueError(f"找不到符合條件的樣品: {query}")

    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    strong_gap = second is None or best["score"] - second["score"] >= 0.08

    if best["score"] >= 0.92 and strong_gap:
        return {"status": "resolved", **best, "matches": candidates}

    if best["score"] >= 0.97 and second is None:
        return {"status": "resolved", **best, "matches": candidates}

    return {"status": "ambiguous", "matches": candidates}

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

def update_sample(id, sample_no=None, title=None, fabric_no=None, date_received=None, sampled_date=None, 
                  version=None, printing_environment=None, printing_file_name=None, 
                  remark=None, preview_path=None):
    _ensure_schema()
    # Only updates editable fields
    return execute_db(
        '''UPDATE samples SET 
            sample_no = COALESCE(?, sample_no),
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
        (sample_no, title, fabric_no, date_received, sampled_date, version, printing_environment, printing_file_name, remark, preview_path, id)
    )

def update_sample_by_ai(query, title=None, fabric_no=None, remark=None):
    """
    Finds a sample by its sample_no or title exact/fuzzy match, and updates it.
    If multiple fuzzy matches are found, it returns the list for the AI to ask the user.
    """
    resolved = resolve_sample_for_ai(query)
    if resolved.get("status") == "ambiguous":
        return resolved

    update_sample(resolved['id'], title=title, fabric_no=fabric_no, remark=remark)
    return {
        "status": "success",
        "title": resolved['title'],
        "id": resolved['id'],
        "sample_no": resolved['sample_no'],
        "score": resolved.get("score"),
    }

def list_color_maps(sample_id):
    return query_db('SELECT * FROM sample_color_map WHERE sample_id = ? ORDER BY created_at', (sample_id,))


def deduplicate_color_corrections(sample_id, dedupe_by="rgb", keep="first"):
    rows = list_color_maps(sample_id) or []
    if not rows:
        return {"sample_id": sample_id, "removed_count": 0, "kept_count": 0, "groups": []}

    groups = {}
    ordered_keys = []
    for row in rows:
        if dedupe_by == "rgb+target":
            key = (
                row["rgb_r"], row["rgb_g"], row["rgb_b"],
                row["target_mode"], row["target_l"], row["target_a"], row["target_b"], row["target_note"],
            )
        else:
            key = (row["rgb_r"], row["rgb_g"], row["rgb_b"])
        if key not in groups:
            groups[key] = []
            ordered_keys.append(key)
        groups[key].append(row)

    ids_to_delete = []
    duplicate_groups = []
    for key in ordered_keys:
        items = groups[key]
        if len(items) <= 1:
            continue
        keeper = items[-1] if keep == "last" else items[0]
        to_remove = items[:-1] if keep == "last" else items[1:]
        ids_to_delete.extend([item["id"] for item in to_remove])
        duplicate_groups.append({
            "rgb": [items[0]["rgb_r"], items[0]["rgb_g"], items[0]["rgb_b"]],
            "count": len(items),
            "kept_id": keeper["id"],
            "removed_ids": [item["id"] for item in to_remove],
        })

    if ids_to_delete:
        placeholders = ",".join("?" for _ in ids_to_delete)
        execute_db(
            f"DELETE FROM sample_color_map WHERE sample_id = ? AND id IN ({placeholders})",
            (sample_id, *ids_to_delete),
        )

    return {
        "sample_id": sample_id,
        "removed_count": len(ids_to_delete),
        "kept_count": len(rows) - len(ids_to_delete),
        "groups": duplicate_groups,
    }

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
    mode = str(target_mode or '').strip()
    if mode.upper() == 'LAB':
        mode = 'lab'
    elif not mode:
        mode = 'note'
    if hex_val is None and rgb_r is not None and rgb_g is not None and rgb_b is not None:
        hex_val = '#%02x%02x%02x' % (int(rgb_r), int(rgb_g), int(rgb_b))
    return execute_db(
        '''INSERT INTO sample_color_map (
            sample_id, rgb_r, rgb_g, rgb_b, target_mode, 
            target_l, target_a, target_b, target_note,
            pick_x, pick_y, hex
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (sample_id, rgb_r, rgb_g, rgb_b, mode, 
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

