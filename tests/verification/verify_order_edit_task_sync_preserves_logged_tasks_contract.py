import unittest
import os
import sys

# Setup path
sys.path.append(os.path.abspath('src'))

from services.db import init_db, get_conn
from services import order_repo, production_repo, fabric_repo, sample_repo

class TestSyncPreservesLoggedTasks(unittest.TestCase):
    def setUp(self):
        import services.db
        from pathlib import Path
        self.test_db = Path('test_sync_preservation.db')
        if self.test_db.exists():
            os.remove(self.test_db)
        services.db.DB_PATH = self.test_db
        init_db()
        
        # Setup Data
        self.fabric_id = fabric_repo.create_fabric('F001', 'Cotton', 100, 200)
        self.cyl_id = fabric_repo.create_cylinder(self.fabric_id, 'C01')
        self.roll_id = fabric_repo.create_roll(self.cyl_id, 10) # 10kg
        
        self.sample_id1 = sample_repo.create_sample(sample_no='S001', fabric_no='F001')
        self.sample_id2 = sample_repo.create_sample(sample_no='S002', fabric_no='F001')

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

    def test_sync_preserves_logs(self):
        print("\nVerifying Sync Preserves Logged Tasks Contract...")
        
        # 1. Create Order with Item 1
        order_id = order_repo.create_order({
            'order_no': 'ORD-001',
            'items': [{'fabric_no': 'F001', 'sample_id': self.sample_id1, 'quantity': 100}]
        })
        production_repo.sync_tasks_for_order(order_id)
        
        tasks = production_repo.list_tasks(order_id)
        self.assertEqual(len(tasks), 1)
        task1_id = tasks[0]['id']
        
        # 2. Add Log to Task 1
        production_repo.add_log_to_task(task1_id, self.roll_id, 10.0)
        
        # 3. Edit Order: Swap Item 1 for Item 2
        order_repo.update_order(order_id, {
            'order_no': 'ORD-001-v2',
            'items': [{'fabric_no': 'F001', 'sample_id': self.sample_id2, 'quantity': 50}]
        })
        production_repo.sync_tasks_for_order(order_id)
        
        # 4. Check State: Should have 2 tasks
        # Task 1 (S001) should persist because it has logs
        # Task 2 (S002) should be created
        new_tasks = production_repo.list_tasks(order_id)
        self.assertEqual(len(new_tasks), 2, "Should preserve orphaned task and add new one")
        
        t1 = next(t for t in new_tasks if t['id'] == task1_id)
        self.assertEqual(t1['sample_id'], self.sample_id1, "Preserved task should match original sample")
        
        t2 = next(t for t in new_tasks if t['id'] != task1_id)
        self.assertEqual(t2['sample_id'], self.sample_id2, "New task should match new sample")
        
        print("PASSED: Logged task preserved.")
        
        # 5. Edit Order: Remove Item 2 (No logs)
        # Empty items list
        order_repo.update_order(order_id, {'order_no': 'ORD-001-v3', 'items': []})
        production_repo.sync_tasks_for_order(order_id)
        
        # 6. Check State: Should have 1 task (Task 1)
        final_tasks = production_repo.list_tasks(order_id)
        self.assertEqual(len(final_tasks), 1, "Should delete unlogged task but keep logged one")
        self.assertEqual(final_tasks[0]['id'], task1_id)
        
        print("PASSED: Unlogged task deleted.")

if __name__ == "__main__":
    unittest.main()
