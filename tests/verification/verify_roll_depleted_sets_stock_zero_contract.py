import os
import sys
import unittest

# Setup path
sys.path.append(os.path.abspath('src'))

from services.db import init_db, get_conn
from services import production_repo, fabric_repo, order_repo

class TestRollDepleted(unittest.TestCase):
    def setUp(self):
        self.db_path = 'src/data/test_roll_depleted_gate.db'
        if os.path.exists(self.db_path): os.remove(self.db_path)
        import services.db
        services.db.DB_PATH = os.path.abspath(self.db_path)
        init_db()
        
        # Setup Data
        fid = fabric_repo.create_fabric("F1", "Cotton", 150, 200)
        cid = fabric_repo.create_cylinder(fid, 'C1')
        self.roll_id = fabric_repo.create_roll(cid, 20, 'R1') # Length will be approx 100m
        self.order_id = order_repo.create_order({
            'order_no': 'ORD-DEPLETE', 'customer_name': 'Test', 'items': [{'fabric_no': 'F1', 'quantity': 100}]
        })
        
    def test_depleted_sets_stock_zero_and_logs_history(self):
        print("Verifying roll_depleted contract...")
        
        # Initial check
        r = fabric_repo.get_roll_with_history(self.roll_id)
        self.assertGreater(r['length_m'], 0)
        self.assertEqual(r['status'], 'in_stock')
        
        # Create Task with depletion
        production_repo.create_task({
            'order_id': self.order_id,
            'roll_id': self.roll_id,
            'used_length': 10,
            'status': 'printing',
            'roll_depleted': True
        })
        
        # Check roll
        r_after = fabric_repo.get_roll_with_history(self.roll_id)
        self.assertEqual(r_after['length_m'], 0)
        self.assertEqual(r_after['status'], 'depleted')
        
        # Check history
        history = r_after['history']
        self.assertTrue(len(history) > 0)
        self.assertEqual(history[0]['action'], 'depleted')
        self.assertEqual(history[0]['new_qty'], 0)
        
        print("PASSED")

if __name__ == "__main__":
    unittest.main()
