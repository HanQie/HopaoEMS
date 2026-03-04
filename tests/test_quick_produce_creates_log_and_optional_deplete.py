import os
import sys
import unittest

# Setup path
sys.path.append(os.path.abspath('src'))

from services.db import init_db, get_conn
from services import production_repo, fabric_repo, order_repo

class TestQuickProduceFlow(unittest.TestCase):
    def setUp(self):
        self.db_path = 'src/data/test_produce_flow.db'
        if os.path.exists(self.db_path): os.remove(self.db_path)
        import services.db
        services.db.DB_PATH = os.path.abspath(self.db_path)
        init_db()
        
        # Setup Data
        fid = fabric_repo.create_fabric("F-PRD", "Poly", 100, 100)
        cid = fabric_repo.create_cylinder(fid, 'C1')
        self.roll_id = fabric_repo.create_roll(cid, 50, 'R1') # Approx 450m
        
        self.order_id = order_repo.create_order({
            'order_no': 'ORD-Q', 'customer_name': 'Test', 'items': [{'fabric_no': 'F-PRD', 'quantity': 100}]
        })
        
        self.task_id = production_repo.create_task({
            'order_id': self.order_id,
            'roll_id': None, # Start empty
            'used_length': 0,
            'status': 'printing'
        })
        
    def test_quick_produce_creates_log_and_depletes(self):
        print("Testing Quick Produce Flow...")
        
        # 1. Produce 50m
        log_id = production_repo.add_log_to_task(self.task_id, self.roll_id, 50.0, roll_depleted=False)
        
        # Check logs
        logs = production_repo.list_logs_by_task(self.task_id)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['length'], 50.0)
        
        # Check Roll (Should NOT change stock)
        r = fabric_repo.get_roll_with_history(self.roll_id)
        self.assertGreater(r['length_m'], 400) # Still full
        
        # 2. Produce & Deplete
        log_id_2 = production_repo.add_log_to_task(self.task_id, self.roll_id, 20.0, roll_depleted=True)
        
        # Check Roll (Stock 0)
        r2 = fabric_repo.get_roll_with_history(self.roll_id)
        self.assertEqual(r2['length_m'], 0)
        self.assertEqual(r2['status'], 'depleted')
        
        # Check History
        h = r2['history'][0]
        self.assertEqual(h['action'], 'depleted')
        self.assertEqual(h['source'], 'production_roll_depleted')
        self.assertIn(str(log_id_2), h['note'])
        
        print("PASSED")

if __name__ == "__main__":
    unittest.main()
