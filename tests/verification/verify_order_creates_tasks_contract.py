import unittest
import os
import sys

# Setup path
sys.path.append(os.path.abspath('src'))

from services.db import init_db, get_conn
from services import order_repo, production_repo, fabric_repo, sample_repo

class TestOrderCreatesTasksContract(unittest.TestCase):
    def setUp(self):
        # Initialize In-Memory DB or fresh test file logic? 
        # Since code uses 'app.db', to test strictly we might need a test db override.
        # But `verify_` scripts usually run against actual code logic.
        # I'll rely on a temporary DB or the fact that services allow injection?
        # services/db.py uses a hardcoded DB_PATH unless we patch it.
        # For verification, I'll patch `services.db.DB_PATH` if possible or assume test environment.
        # Actually I can just use `init_db` on a test db.
        
        # Patching DB_PATH
        import services.db
        from pathlib import Path
        self.test_db = Path('test_order_creates_tasks_contract.db')
        if self.test_db.exists():
            os.remove(self.test_db)
        services.db.DB_PATH = self.test_db
        init_db()
        
        # Setup Data
        self.fabric_id = fabric_repo.create_fabric('F001', 'Cotton', 100, 200)
        self.sample_id = sample_repo.create_sample(sample_no='S001', fabric_no='F001')
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
                pass # Retry or ignore in test tearDown on windows

    def test_create_order_generates_tasks(self):
        print("\nVerifying Order Creates Tasks Contract...")
        
        # 1. Create Order with 2 Items
        payload = {
            'order_no': 'ORD-TEST-001',
            'customer_name': 'Test Customer',
            'items': [
                {'fabric_no': 'F001', 'sample_id': self.sample_id, 'quantity': 100, 'note': 'Item 1'},
                {'fabric_no': 'F001', 'sample_id': self.sample_id2, 'quantity': 50, 'note': 'Item 2'}
            ]
        }
        
        order_id = order_repo.create_order(payload)
        
        # 2. Trigger Sync (Simulating UI behavior)
        production_repo.sync_tasks_for_order(order_id)
        
        # 3. Verify Tasks
        tasks = production_repo.list_tasks(order_id)
        
        self.assertEqual(len(tasks), 2, "Should create exactly 2 tasks")
        
        # Sort by sample_id to check deterministic
        tasks.sort(key=lambda x: x['sample_id'])
        
        t1 = tasks[0]
        self.assertEqual(t1['sample_id'], self.sample_id)
        self.assertEqual(t1['target_qty'], 100.0)
        self.assertEqual(t1['fabric_no'], 'F001')
        self.assertEqual(t1['note'], 'Item 1')
        
        t2 = tasks[1]
        self.assertEqual(t2['sample_id'], self.sample_id2)
        self.assertEqual(t2['target_qty'], 50.0)
        
        print("PASSED: Order creation correctly generated corresponding tasks.")

if __name__ == "__main__":
    unittest.main()
