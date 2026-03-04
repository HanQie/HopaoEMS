import unittest
import os
import sys

sys.path.append(os.path.abspath('src'))

from services.db import init_db
from services import production_repo, fabric_repo

class TestTaskDoneGate(unittest.TestCase):
    def setUp(self):
        import services.db
        from pathlib import Path
        self.test_db = Path('test_task_done_gate.db')
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

    def test_complete_task_requires_zero_unwashed(self):
        print("\nVerifying Task Done Requires Zero Unwashed Logs...")
        
        # 1. No logs -> Can complete
        self.assertTrue(production_repo.can_complete_task(self.task_id))
        
        # 2. Add unwashed log
        log_id = production_repo.add_log_to_task(self.task_id, self.roll_id, 10)
        self.assertFalse(production_repo.can_complete_task(self.task_id), "Should not allow complete if unwashed logs exist")
        
        # 3. Try complete -> Should fail
        success = production_repo.complete_task(self.task_id)
        self.assertFalse(success, "complete_task should return False")
        t = production_repo.get_task(self.task_id)
        self.assertNotEqual(t['status'], 'done')

        # 4. Wash log
        production_repo.mark_logs_washed([log_id])
        self.assertTrue(production_repo.can_complete_task(self.task_id))
        
        # 5. Complete
        success = production_repo.complete_task(self.task_id)
        self.assertTrue(success)
        t = production_repo.get_task(self.task_id)
        self.assertEqual(t['status'], 'done')
        
        print("PASSED: Task Done Gate enforced.")

if __name__ == "__main__":
    unittest.main()
