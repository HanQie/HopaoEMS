import unittest
import os
import sys

sys.path.append(os.path.abspath('src'))

from services.db import init_db
from services import order_repo, production_repo, fabric_repo, sample_repo

class TestOrderCloseGate(unittest.TestCase):
    def setUp(self):
        import services.db
        from pathlib import Path
        self.test_db = Path('test_order_close_strict_gate.db')
        if self.test_db.exists():
            try: os.remove(self.test_db)
            except: pass
        services.db.DB_PATH = self.test_db
        init_db()
        
        self.fabric_id = fabric_repo.create_fabric('F001', 'Cotton', 100, 200)
        self.cyl_id = fabric_repo.create_cylinder(self.fabric_id, 'C1')
        self.roll_id = fabric_repo.create_roll(self.cyl_id, 100)
        self.sample_id = sample_repo.create_sample('S1', 'F001')

    def tearDown(self):
        import gc
        import time
        gc.collect()
        time.sleep(0.1)
        if self.test_db.exists():
            try: os.remove(self.test_db)
            except: pass

    def test_order_close_requirements(self):
        print("\nVerifying Order Close Requires All Tasks Done & Zero Unwashed Logs...")
        
        # 1. Create Order + Task
        order_id = order_repo.create_order({'items': [{'fabric_no': 'F001', 'sample_id': self.sample_id, 'quantity': 10}]})
        production_repo.sync_tasks_for_order(order_id)
        task_id = production_repo.list_tasks(order_id)[0]['id']
        
        # 2. Add Log (Unwashed)
        log_id = production_repo.add_log_to_task(task_id, self.roll_id, 10)
        
        # 3. Check Gate: Task not done, Log unwashed -> Fail
        self.assertFalse(production_repo.can_close_order(order_id))
        self.assertFalse(production_repo.close_order(order_id))
        
        # 4. Wash Log
        production_repo.mark_logs_washed([log_id])
        # Task still printing (manual flow now)
        t = production_repo.get_task(task_id)
        self.assertEqual(t['status'], 'printing')
        
        # 5. Check Gate: Task not done -> Fail
        self.assertFalse(production_repo.can_close_order(order_id))
        
        # 6. Mark Task Done
        production_repo.complete_task(task_id)
        
        # 7. Check Gate: All done + no unwashed -> Pass
        self.assertTrue(production_repo.can_close_order(order_id))
        self.assertTrue(production_repo.close_order(order_id))
        
        o = order_repo.get_order(order_id)
        self.assertEqual(o['status'], 'closed')
        
        # 8. Add unwashed log to DONE task -> Should REOPEN Order and Task
        # Logic in sync_task_and_order_status handles reopening if unwashed logs added
        production_repo.add_log_to_task(task_id, self.roll_id, 5)
        
        t = production_repo.get_task(task_id)
        o = order_repo.get_order(order_id)
        self.assertEqual(t['status'], 'printing', "Task should reopen on unwashed log")
        self.assertEqual(o['status'], 'printing', "Order should reopen on unwashed log")
        
        print("PASSED: Order Close Gate enforced.")

if __name__ == "__main__":
    unittest.main()
