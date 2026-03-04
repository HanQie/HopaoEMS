
import os
import sys
import shutil
import sqlite3
import datetime

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, src_path)

from hopaoems.app_factory import create_app
from hopaoems.services.schema_migrations import init_schema
from hopaoems.services.db import get_db, execute_db, close_db

# Whitelist for deletion
ALLOWED_DELETES = [
    os.path.abspath(os.path.join(src_path, 'instance', 'hopaoems.sqlite')),
    os.path.abspath(os.path.join(src_path, 'hopaoems', 'instance', 'hopaoems_smoke_test.sqlite')),
]

def clean_database():
    print("--- [CLEANROOM] Step 1: Cleaning Databases ---")
    deleted_files = []
    
    # 1. DB Files
    for db_path in ALLOWED_DELETES:
        if os.path.exists(db_path):
            print(f"  Deleting: {db_path}")
            try:
                os.remove(db_path)
                deleted_files.append(db_path)
            except Exception as e:
                print(f"  ERROR deleting {db_path}: {e}")
                sys.exit(1)
        else:
            print(f"  Skipping (Not Found): {db_path}")

    # 2. Preview Images (Optional per spec, but good for clean state)
    # Only delete specific test files to avoid wiping user data if not intended
    # Spec says: "src/data/uploads/samples/ 內的 preview 圖檔（只清 sample，不清整個 uploads 根）"
    # We will assume 'src/data' is relative to root.
    # The app config usually points to instance/uploads or similar. 
    # Let's rely on app config later or just skip this for safety unless strictly required.
    # User said: "（可選）... （只清 sample ...）"
    # Let's clean safely by checking a known test pattern if possible, or just skip to be safe designated by user "Cleanroom".
    # User said: "目標... 刪除本機資料庫... 重建 schema"
    # Let's stick to DBs for now to be safe.
    
    print("  Cleaned files:", deleted_files)
    return True

def create_preview_image(app):
    """Create a minimal preview image for testing."""
    upload_dir = app.config['SAMPLES_UPLOAD_DIR']
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    # Create a 1x1 red png
    # Minimal binary for a PNG
    # 1x1 red pixel
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
    
    path = os.path.join(upload_dir, 'clean_room_sample.png')
    with open(path, 'wb') as f:
        f.write(png_data)
    return 'clean_room_sample.png'

def seed_minimal_data(app):
    print("--- [CLEANROOM] Step 2: Seeding Minimal Data ---")
    with app.app_context():
        # 1. Init Schema
        init_schema()
        
        db = get_db()
        
        # 2. Seed Data
        # Users are already seeded by init_schema (admin/viewer)
        
        # Fabric
        print("  Seeding Fabric/Rolls...")
        execute_db("INSERT INTO fabrics (id, fabric_code, material, width_cm, yard_weight_gyd) VALUES (1, 'F-CLEAN', 'Cotton', 150, 300)")
        execute_db("INSERT INTO cylinders (id, fabric_id, cylinder_no) VALUES (1, 1, 'V-CLEAN')")
        # Roll 1: In Stock
        execute_db("INSERT INTO rolls (id, cylinder_id, roll_no, length_m, status) VALUES (1, 1, 'R-CLEAN-1', 100, 'in_stock')")
        # Roll 2: Depleted
        execute_db("INSERT INTO rolls (id, cylinder_id, roll_no, length_m, status) VALUES (2, 1, 'R-CLEAN-2', 0, 'depleted')")
        
        # Sample
        print("  Seeding Sample...")
        preview_path = create_preview_image(app)
        execute_db("INSERT INTO samples (id, sample_no, title, fabric_no, preview_path) VALUES (1, 'S-CLEAN', 'Clean Room Sample', 'F-CLEAN', ?)", (preview_path,))
        
        # Order / Task
        print("  Seeding Order/Task...")
        execute_db("INSERT INTO orders (id, order_no, status, received_date) VALUES (1, 'ORD-CLEAN', 'open', '2026-02-01')")
        execute_db("INSERT INTO order_items (id, order_id, fabric_no, sample_id, qty) VALUES (1, 1, 'F-CLEAN', 1, 100)")
        execute_db("INSERT INTO production_tasks (id, order_id, order_item_id, sample_id, fabric_no, target_qty, status) VALUES (1, 1, 1, 1, 'F-CLEAN', 100, 'printing')")
        
        # Production Logs
        print("  Seeding Logs...")
        # Log 1: Unwashed (Task 1, Roll 1)
        execute_db("INSERT INTO production_logs (id, task_id, roll_id, length, operator_id, status) VALUES (1, 1, 1, 10, 1, 'unwashed')")
        
        # Log 2: Washed (Task 1, Roll 1)
        execute_db("INSERT INTO wash_sessions (id, vat_code, roll_count, total_length, operator_id) VALUES (1, 'V-CLEAN', 1, 20, 1)")
        
        execute_db("INSERT INTO production_logs (id, task_id, roll_id, length, operator_id, status, washed_at, wash_session_id) VALUES (2, 1, 1, 20, 1, 'washed', '2026-02-10 10:00:00', 1)")
        
        # Update Task Usage
        execute_db("UPDATE production_tasks SET used_length = 30 WHERE id = 1")
        # Update Roll Usage (Roll 1 started at 100, used 30 -> 70)
        execute_db("UPDATE rolls SET length_m = 70 WHERE id = 1")
        
        print("  Seed Complete.")
        db.commit()

def run_gates():
    print("--- [CLEANROOM] Step 3: Running Gates ---")
    
    # Import run_gates from contracts
    # We need to handle the sys.path specifically for contracts
    contract_path = os.path.join(src_path, 'hopaoems', 'contracts')
    sys.path.append(contract_path)
    
    # We execute it as a subprocess to ensure clean environment (imports, global vars)
    # OR we can import. Subprocess is safer for state isolation.
    import subprocess
    gate_script = os.path.join(contract_path, 'run_gates.py')
    
    print(f"  Executing: {gate_script}")
    
    # Run twice as requested
    for i in range(1, 3):
        print(f"  >> Run #{i} <<")
        result = subprocess.run([sys.executable, gate_script], capture_output=True, text=True)
        
        print(result.stdout)
        if result.returncode != 0:
            print(f"  [FAIL] Run #{i} failed with return code {result.returncode}")
            print("  --- STDERR ---")
            print(result.stderr)
            return False
            
    return True

if __name__ == "__main__":
    if not clean_database():
        sys.exit(1)
        
    app = create_app()
    seed_minimal_data(app)
    
    if run_gates():
        print("\n=== CLEANROOM PASS ===")
    else:
        print("\n=== CLEANROOM FAIL ===")
        sys.exit(1)
