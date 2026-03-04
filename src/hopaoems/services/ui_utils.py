
import hashlib

def get_vat_tone_idx(vat_code, n=8):
    """
    Generate a deterministic tone index (0 to n-1) based on vat_code.
    Normalization: trim, uppercase.
    """
    if not vat_code:
        return 0
    clean_code = str(vat_code).strip().upper()
    
    # Use MD5 for deterministic hashing (stable across restarts)
    h = hashlib.md5(clean_code.encode('utf-8')).hexdigest()
    return int(h, 16) % n

def get_pagination(total, page, page_size):
    """
    Compute pagination metadata.
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < total_pages else None,
        'items': [] # This will be filled with page numbers for the UI
    }

