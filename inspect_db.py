
import sqlite3
import os

db_path = 'instance/hopaoems.sqlite'
print(f"Connecting to: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print("\n--- Schema of 'samples' ---")
    
    # Check if table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='samples'")
    if not cur.fetchone():
        print("Table 'samples' DOES NOT EXIST!")
    else:
        # Get schema
        cur.execute("PRAGMA table_info(samples)")
        cols = cur.fetchall()
        for col in cols:
            print(col)
            
        print("\n--- First 5 rows of 'samples' ---")
        cur.execute("SELECT * FROM samples LIMIT 5")
        rows = cur.fetchall()
        for row in rows:
            print(row)
            
        if rows:
            first_id = rows[0][0] # Assuming id is first column (index 0)
            print(f"\nChecking lookup for ID {first_id} (type: {type(first_id)})")
            
            # Lookup with int
            print(f"Executing: SELECT * FROM samples WHERE id = {first_id}")
            cur.execute("SELECT * FROM samples WHERE id = ?", (first_id,))
            res = cur.fetchone()
            print(f"Result (int match): {res is not None}")
            
            # Lookup with string
            print(f"Executing: SELECT * FROM samples WHERE id = '{first_id}'")
            cur.execute("SELECT * FROM samples WHERE id = ?", (str(first_id),))
            res_str = cur.fetchone()
            print(f"Result (str match): {res_str is not None}")

    conn.close()
except Exception as e:
    print(f"Error: {e}")
