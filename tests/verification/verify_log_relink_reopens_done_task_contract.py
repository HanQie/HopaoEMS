import os
import sys
import unittest

# Setup path
sys.path.append(os.path.abspath('src'))

from services.db import init_db, get_conn
from services import production_repo, fabric_repo, order_repo

class TestLogRelinkStatus(unittest.TestCase):
    def setUp(self):
        self.db_path = 'src/data/test_relink_gate.db'
        if os.path.exists(self.db_path): os.remove(self.db_path)
        import services.db
        services.db.DB_PATH = os.path.abspath(self.db_path)
        init_db()
        
        # Setup Data
        fid = fabric_repo.create_fabric("F1", "Cotton", 150, 200)
        conn = get_conn()
        conn.execute("INSERT INTO cylinders (fabric_id, cylinder_no) VALUES (?, 'C1')", (fid,))
        conn.execute("INSERT INTO rolls (cylinder_id, roll_no, weight_kg, length_m, status) VALUES (1, 'R1', 20, 100, 'in_stock')")
        self.roll_id = 1
        conn.commit()
        conn.close()
        
        self.order_id = order_repo.create_order({
            'order_no': 'ORD-GATE-1', 'customer_name': 'Test', 'items': [{'fabric_no': 'F1', 'quantity': 100}]
        })
        
        self.task_a = production_repo.create_task({
            'order_id': self.order_id, 'roll_id': self.roll_id, 'used_length': 10, 'status': 'done'
        })
        self.task_b = production_repo.create_task({
            'order_id': self.order_id, 'roll_id': self.roll_id, 'used_length': 20, 'status': 'printing'
        })
        
    def test_relink_reopens_done_task(self):
        print("Verifying log relink reopens done task contract...")
        logs_b = [l for l in production_repo.list_unwashed_logs() if l['task_id'] == self.task_b]
        log_id = logs_b[0]['id']
        production_repo.set_production_status(self.task_a, 'done')
        production_repo.relink_log(log_id, self.task_a)
        task_a_after = production_repo.get_task(self.task_a)
        self.assertNotEqual(task_a_after['status'], 'done')
        print("PASSED")

if __name__ == "__main__":
    unittest.main()
