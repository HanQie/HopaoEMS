import unittest
import os
import sys

sys.path.append(os.path.abspath('src'))

from services.db import init_db
from services import order_repo, production_repo, fabric_repo, sample_repo

class TestTaskDoneFlow(unittest.TestCase):
    def setUp(self):
        import services.db
        from pathlib import Path
        self.test_db = Path('test_task_done_flow.db')
        if self.test_db.exists():
            try: os.remove(self.test_db)
            except: pass
        services.db.DB_PATH = self.test_db
        init_db()
        
        self.fabric_id = fabric_repo.create_fabric('F001', 'Cotton', 100, 200)
        self.cyl_id = fabric_repo.create_cylinder(self.fabric_id, 'C1')
        self.roll_id = fabric_repo.create_roll(self.cyl_id, 100)
        self.task_id = production_repo.create_task({'roll_id': self.roll_id, 'used_length': 0})

    def tearDown(self):
        import gc
        import time
        gc.collect()
        time.sleep(0.1)
        if self.test_db.exists():
            try: os.remove(self.test_db)
            except: pass

    def test_flow(self):
        print("\nTesting Task Done Flow...")
        # 1. Start printing
        t = production_repo.get_task(self.task_id)
        self.assertEqual(t['status'], 'printing')
        
        # 2. Add log, Wash log
        log_id = production_repo.add_log_to_task(self.task_id, self.roll_id, 10)
        production_repo.mark_logs_washed([log_id])
        
        # 3. Manual Done
        production_repo.complete_task(self.task_id)
        
        t = production_repo.get_task(self.task_id)
        self.assertEqual(t['status'], 'done')
        print("PASSED: Task Done Flow")

if __name__ == "__main__":
    unittest.main()
