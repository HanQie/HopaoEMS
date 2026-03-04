import sqlite3
import os
import sys

def verify_order_schema_contract():
    print("Verifying Order Schema Contract...")
    db_path = os.path.join('src', 'data', 'app.db')
    if not os.path.exists(db_path):
        print(f"FAILED: Database not found at {db_path}")
        sys.exit(1)
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    errors = []
    
    # Check orders table
    orders_cols = [row[1] for row in c.execute("PRAGMA table_info(orders)").fetchall()]
    required_orders = ['order_no', 'received_date', 'due_date', 'note']
    for col in required_orders:
        if col not in orders_cols:
            errors.append(f"Missing column in 'orders': {col}")
            
    # Check order_items table
    items_cols = [row[1] for row in c.execute("PRAGMA table_info(order_items)").fetchall()]
    required_items = ['fabric_no', 'sample_id', 'qty', 'note']
    for col in required_items:
        if col not in items_cols:
            errors.append(f"Missing column in 'order_items': {col}")
            
    conn.close()
    
    if errors:
        print("FAILED")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)
    else:
        print("PASSED")
        sys.exit(0)

if __name__ == "__main__":
    verify_order_schema_contract()
