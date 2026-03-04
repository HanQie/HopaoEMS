import sqlite3
import os
import sys

def verify_sample_fabric_link_contract():
    print("Verifying Sample-Fabric Link Contract...")
    db_path = os.path.join('src', 'data', 'app.db')
    if not os.path.exists(db_path):
        print(f"FAILED: Database not found at {db_path}")
        sys.exit(1)
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Get all fabrics
    fabrics = [row['fabric_code'] for row in c.execute("SELECT fabric_code FROM fabrics").fetchall()]
    fabric_set = set(fabrics)
    
    # 2. Get all samples
    samples = c.execute("SELECT id, fabric_no, sample_no FROM samples").fetchall()
    total_samples = len(samples)
    
    # 3. Analyze
    cols = [row[1] for row in c.execute("PRAGMA table_info(samples)").fetchall()]
    has_col = 'fabric_no' in cols
    
    fabric_no_present = 0
    match_count = 0
    orphan_count = 0
    dropped_count = 0
    fabric_counts = {}
    
    for s in samples:
        f_no = s['fabric_no']
        if f_no and str(f_no).strip():
            fabric_no_present += 1
            if f_no in fabric_set:
                match_count += 1
                fabric_counts[f_no] = fabric_counts.get(f_no, 0) + 1
            else:
                orphan_count += 1
        else:
            dropped_count += 1
            
    # Sort top 5
    top5 = sorted(fabric_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    print(f"Summary:")
    print(f"- Total samples: {total_samples}")
    print(f"- Has 'fabric_no' column: {has_col}")
    print(f"- Samples with non-empty fabric_no: {fabric_no_present}")
    print(f"- MATCHed (fabric exists): {match_count}")
    print(f"- ORPHAN (fabric missing): {orphan_count}")
    print(f"- DROPPED (empty/null): {dropped_count}")
    print(f"- Top 5 Fabrics: {top5}")
    
    if match_count == 0 and total_samples > 0:
        print("CONCLUSION: Data link missing (Data Issue, not Order issue)")
        # Fail the gate if we have samples but zero links
        sys.exit(1)
    else:
        print("PASSED")
        sys.exit(0)

if __name__ == "__main__":
    verify_sample_fabric_link_contract()
