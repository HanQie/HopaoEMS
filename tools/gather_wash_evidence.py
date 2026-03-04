
import sys
import os
import json
from flask import url_for

# Setup paths
sys.path.append(os.path.join(os.getcwd(), 'src'))

from hopaoems.app_factory import create_app
from hopaoems.services import db, schema_migrations, auth_service
from bs4 import BeautifulSoup

def get_evidence():
    db_path = 'evidence_test.sqlite'
    if os.path.exists(db_path):
        os.remove(db_path)
        
    app = create_app({'TESTING': True, 'DATABASE': db_path, 'WTF_CSRF_ENABLED': False})
    
    with app.test_client() as client:
        with app.app_context():
            schema_migrations.init_schema()
            
            # Seed data
            # 1. User
            db.execute_db("INSERT INTO users (id, username, password_hash, role) VALUES (1, 'op', 'hash', 'operator')")
            db.execute_db("INSERT INTO users (id, username, password_hash, role) VALUES (2, 'vi', 'hash', 'viewer')")
            
            # 2. Domain data
            db.execute_db("INSERT INTO orders (id, order_no, status) VALUES (10, 'ORD-EVIDENCE', 'open')")
            db.execute_db("INSERT INTO samples (id, sample_no, title) VALUES (10, 'S-EVIDENCE', 'Evidence Sample')")
            db.execute_db("INSERT INTO fabrics (id, fabric_code) VALUES (10, 'F-EVIDENCE')")
            db.execute_db("INSERT INTO cylinders (id, fabric_id, cylinder_no) VALUES (10, 10, 'VAT-EVIDENCE')")
            db.execute_db("INSERT INTO rolls (id, cylinder_id, roll_no, length_m) VALUES (10, 10, 'ROLL-EVIDENCE', 100)")
            db.execute_db("INSERT INTO production_tasks (id, order_id, sample_id, fabric_no, status, target_qty) VALUES (10, 10, 10, 'F-EVIDENCE', 'printing', 50)")
            
            # 3. Washed Log
            log_id = 99
            db.execute_db(f"""
                INSERT INTO production_logs 
                (id, task_id, roll_id, length, operator_id, status, washed_at, wash_session_id) 
                VALUES ({log_id}, 10, 10, 15.5, 1, 'washed', '2026-02-05 10:00:00', 500)
            """)
            db.commit()
            
            # ---------------------------------------------------------
            # EVIDENCE A: Operator View
            # ---------------------------------------------------------
            client.post('/auth/login', data={'username': 'op', 'password': 'op'})
            res = client.get('/production/task/10')
            soup = BeautifulSoup(res.data, 'html.parser')
            # Find the actions cell (contains 'Undo Wash' or similar)
            action_cell_op = ""
            for td in soup.find_all('td'):
                if 'undo' in td.get_text().lower() or 'wash' in td.get_text().lower():
                    # We want the one with the link
                    if td.find('a', href=True) and '/undo' in td.find('a')['href']:
                        action_cell_op = td.prettify()
                        break
            
            # ---------------------------------------------------------
            # EVIDENCE B: Viewer View
            # ---------------------------------------------------------
            client.post('/auth/logout')
            client.post('/auth/login', data={'username': 'vi', 'password': 'vi'})
            res = client.get('/production/task/10')
            soup = BeautifulSoup(res.data, 'html.parser')
            # Find the actions cell for task 10
            action_cell_vi = ""
            # Since viewer doesn't see the link, we look for the cell that would contain it
            # We'll just find the last TD in the row for ROLL-EVIDENCE
            rows = soup.find_all('tr')
            for row in rows:
                if 'ROLL-EVIDENCE' in row.get_text():
                    tds = row.find_all('td')
                    if tds:
                        action_cell_vi = tds[-1].prettify()
            
            # ---------------------------------------------------------
            # EVIDENCE C: Undo Confirm Page
            # ---------------------------------------------------------
            client.post('/auth/logout')
            client.post('/auth/login', data={'username': 'op', 'password': 'op'})
            res = client.get(f'/wash/log/{log_id}/undo')
            confirm_html = res.data.decode('utf-8')
            
            # ---------------------------------------------------------
            # EVIDENCE D & E: Undo POST + Change Check + Redirect
            # ---------------------------------------------------------
            log_before = db.query_db("SELECT washed_at, wash_session_id FROM production_logs WHERE id = ?", (log_id,), one=True)
            
            next_target = '/production/task/10?undo=success'
            res = client.post(f'/wash/log/{log_id}/undo?next={next_target}', follow_redirects=False)
            redirect_location = res.headers.get('Location')
            
            log_after = db.query_db("SELECT washed_at, wash_session_id FROM production_logs WHERE id = ?", (log_id,), one=True)

            print("--- EVIDENCE START ---")
            print(f"EVIDENCE_A_HTML:\n{action_cell_op}")
            print(f"EVIDENCE_B_HTML:\n{action_cell_vi}")
            print(f"EVIDENCE_C_CONFIRM_HTML:\n{confirm_html}")
            print(f"EVIDENCE_D_BEFORE: washed_at={log_before['washed_at']}, session={log_before['wash_session_id']}")
            print(f"EVIDENCE_D_AFTER: washed_at={log_after['washed_at']}, session={log_after['wash_session_id']}")
            print(f"EVIDENCE_E_REDIRECT_LOCATION: {redirect_location}")
            print("--- EVIDENCE END ---")

if __name__ == "__main__":
    try:
        get_evidence()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
