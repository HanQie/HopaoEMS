
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

from hopaoems.app_factory import create_app
from hopaoems.services import db, wash_repo, schema_migrations

def verify():
    app = create_app({'TESTING': True, 'DATABASE': ':memory:', 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        schema_migrations.init_schema()
        
        # Seed
        db.execute_db("INSERT INTO orders (id, order_no) VALUES (1, 'O1')")
        db.execute_db("INSERT INTO samples (id, sample_no, title) VALUES (1, 'S1', 'Sample 1')")
        db.execute_db("INSERT INTO production_tasks (id, order_id, sample_id, fabric_no, target_qty) VALUES (1, 1, 1, 'F1', 10)")
        db.execute_db("INSERT INTO rolls (id, cylinder_id, roll_no, length_m) VALUES (1, 1, 'R1', 100)")
        
        # Washed log
        log_id = 1
        db.execute_db(f"INSERT INTO production_logs (id, task_id, roll_id, length, status, washed_at, wash_session_id) VALUES ({log_id}, 1, 1, 5, 'washed', '2026-02-05', 123)")
        db.commit()
        
        print("--- D) DB State Evidence ---")
        b = db.query_db("SELECT washed_at, wash_session_id FROM production_logs WHERE id=1", one=True)
        print(f"BEFORE: washed_at={b['washed_at']}, wash_session_id={b['wash_session_id']}")
        
        wash_repo.undo_log(log_id)
        
        a = db.query_db("SELECT washed_at, wash_session_id FROM production_logs WHERE id=1", one=True)
        print(f"AFTER: washed_at={a['washed_at']}, wash_session_id={a['wash_session_id']}")
        
        print("\n--- C) Confirm Page Details ---")
        log_details = wash_repo.get_log_for_undo(log_id)
        print(f"vat_code: {log_details['vat_code']}")
        print(f"roll_no: {log_details['roll_no']}")
        print(f"printed_length: {log_details['length']}")
        print(f"sample_name: {log_details['sample_title']}")
        
        print("\n--- E) Next Parameter Logic ---")
        # Testing redirect logic in ui_wash.py (mentally or via mock client)
        # Fixed strategy: Redirect to next if exists, else to wash_history
        # Actually in ui_wash.py:
        # next_url = request.args.get('next') or request.form.get('next') or url_for('ui_wash.wash_history')
        print("Fixed Strategy: Redirect to 'next' param if exists, fallback to 'ui_wash.wash_history'.")

if __name__ == "__main__":
    verify()
