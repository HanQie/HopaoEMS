import unittest
import os
import sys

sys.path.append(os.path.abspath('src'))

from services.db import init_db
from services import order_repo, production_repo, fabric_repo, sample_repo

class TestOrderCloseFlow(unittest.TestCase):
    def setUp(self):
        import services.db
        from pathlib import Path
        self.test_db = Path('test_order_close_flow.db')
        if self.test_db.exists():
            try: os.remove(self.test_db)
            except: pass
        services.db.DB_PATH = self.test_db
        init_db()
        
        self.fabric_id = fabric_repo.create_fabric('F001', 'Cotton', 100, 200)
        self.sample_id = sample_repo.create_sample('S1', 'F001')

    def tearDown(self):
        import gc
        import time
        gc.collect()
        time.sleep(0.1)
        if self.test_db.exists():
            try: os.remove(self.test_db)
            except: pass

    def test_flow(self):
        print("\nTesting Order Close Flow...")
        # 1. Order + Task
        order_id = order_repo.create_order({'items': [{'fabric_no': 'F001', 'sample_id': self.sample_id, 'quantity': 10}]})
        production_repo.sync_tasks_for_order(order_id)
        task_id = production_repo.list_tasks(order_id)[0]['id']
        
        # 2. Mark Task Done (Assuming no logs for simplicity, or 0 unwashed)
        production_repo.complete_task(task_id)
        
        # 3. Close Order
        production_repo.close_order(order_id)
        
        o = order_repo.get_order(order_id)
        self.assertEqual(o['status'], 'closed')
        print("PASSED: Order Close Flow")

if __name__ == "__main__":
    unittest.main()
