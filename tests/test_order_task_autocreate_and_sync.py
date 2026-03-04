import unittest
import os
import sys

sys.path.append(os.path.abspath('src'))

from services.db import init_db
from services import order_repo, production_repo, fabric_repo, sample_repo

class TestOrderTaskSync(unittest.TestCase):
    def setUp(self):
        import services.db
        from pathlib import Path
        self.test_db = Path('test_order_task_sync.db')
        if self.test_db.exists():
            os.remove(self.test_db)
        services.db.DB_PATH = self.test_db
        init_db()
        
        # Setup
        self.fabric_id = fabric_repo.create_fabric('F001', 'Cotton', 100, 200)
        self.sample_id = sample_repo.create_sample('S001', 'F001')

    def tearDown(self):
        import gc
        import time
        gc.collect()
        time.sleep(0.1)
        if self.test_db.exists():
            try:
                os.remove(self.test_db)
            except PermissionError:
                pass

    def test_flow(self):
        # Create Order
        print("\nTesting Order Task Sync Flow...")
        order_id = order_repo.create_order({
            'order_no': 'ORD-FLOW',
            'items': [{'fabric_no': 'F001', 'sample_id': self.sample_id, 'quantity': 500}]
        })
        production_repo.sync_tasks_for_order(order_id)
        
        # Verify Task
        tasks = production_repo.list_tasks(order_id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['target_qty'], 500.0)
        
        # Edit Order (Change Qty)
        order_repo.update_order(order_id, {
            'order_no': 'ORD-FLOW',
            'items': [{'fabric_no': 'F001', 'sample_id': self.sample_id, 'quantity': 600}]
        })
        production_repo.sync_tasks_for_order(order_id)
        
        # Verify Task Updated
        tasks = production_repo.list_tasks(order_id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]['target_qty'], 600.0)
        
        print("PASSED: Order Task Sync Flow")

if __name__ == "__main__":
    unittest.main()
