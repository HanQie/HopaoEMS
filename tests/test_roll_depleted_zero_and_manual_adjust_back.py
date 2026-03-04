import os
import sys
import unittest

# Setup path
sys.path.append(os.path.abspath('src'))

from services.db import init_db, get_conn
from services import production_repo, fabric_repo, order_repo

class TestRollDepletedFlow(unittest.TestCase):
    def setUp(self):
        self.db_path = 'src/data/test_depletion_flow.db'
        if os.path.exists(self.db_path): os.remove(self.db_path)
        import services.db
        services.db.DB_PATH = os.path.abspath(self.db_path)
        init_db()
        
        # Setup Data
        fid = fabric_repo.create_fabric("F1", "Cotton", 150, 200)
        cid = fabric_repo.create_cylinder(fid, 'C1')
        self.roll_id = fabric_repo.create_roll(cid, 20, 'R1')
        self.order_id = order_repo.create_order({
            'order_no': 'ORD-FLOW', 'customer_name': 'Test', 'items': [{'fabric_no': 'F1', 'quantity': 100}]
        })
        
    def test_flow(self):
        # 1. Deplete
        production_repo.create_task({
            'order_id': self.order_id, 'roll_id': self.roll_id, 'used_length': 10, 'status': 'printing', 'roll_depleted': True
        })
        
        r = fabric_repo.get_roll_with_history(self.roll_id)
        self.assertEqual(r['length_m'], 0)
        self.assertEqual(r['status'], 'depleted')
        
        # 2. Manual Adjust Back
        fabric_repo.adjust_roll_stock(self.roll_id, 15.0, "Found extra")
        
        r2 = fabric_repo.get_roll_with_history(self.roll_id)
        self.assertEqual(r2['length_m'], 15.0)
        self.assertEqual(r2['status'], 'in_stock')
        
        history = r2['history']
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['action'], 'manual_adjust') # Most recent
        self.assertEqual(history[1]['action'], 'depleted')

if __name__ == "__main__":
    unittest.main()
