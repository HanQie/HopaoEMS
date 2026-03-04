import os
import sys
import unittest
import tempfile
from flask import url_for

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from hopaoems import create_app
from hopaoems.services import db, schema_migrations

class TestVatGroupingBehavior(unittest.TestCase):
    def setUp(self):
        # Create a temp file for the DB
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'SECRET_KEY': 'test'
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            schema_migrations.init_schema()
            self.setup_data()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def setup_data(self):
        # Create users, fabric, 2 cylinders
        db.execute_db("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", ('admin', 'x', 'operator'))
        db.execute_db("INSERT INTO fabrics (fabric_code) VALUES (?)", ('F1',))
        db.execute_db("INSERT INTO samples (sample_no, title) VALUES (?, ?)", ('S1', 'Sample 1'))
        db.execute_db("INSERT INTO cylinders (fabric_id, cylinder_no) VALUES (?, ?)", (1, 'C1'))
        db.execute_db("INSERT INTO cylinders (fabric_id, cylinder_no) VALUES (?, ?)", (1, 'C2'))
        
        # Roll 1 -> C1, Roll 2 -> C2
        db.execute_db("INSERT INTO rolls (cylinder_id, roll_no, length_m) VALUES (?, ?, ?)", (1, 'R1', 100))
        db.execute_db("INSERT INTO rolls (cylinder_id, roll_no, length_m) VALUES (?, ?, ?)", (2, 'R2', 100))
        
        # Orders and tasks
        db.execute_db("INSERT INTO orders (order_no) VALUES (?)", ('O1',))
        db.execute_db("INSERT INTO production_tasks (order_id, fabric_no, sample_id, target_qty) VALUES (?, ?, ?, ?)", (1, 'F1', 1, 50))
        
        # Logs 1 & 2 -> Roll 1 (C1), Log 3 -> Roll 2 (C2)
        db.execute_db("INSERT INTO production_logs (task_id, roll_id, length) VALUES (?, ?, ?)", (1, 1, 10))
        db.execute_db("INSERT INTO production_logs (task_id, roll_id, length) VALUES (?, ?, ?)", (1, 1, 15))
        db.execute_db("INSERT INTO production_logs (task_id, roll_id, length) VALUES (?, ?, ?)", (1, 2, 20))

    def test_wash_grouping_behavior(self):
        with self.app.app_context():
            from hopaoems.blueprints.ui_wash import _group_by_vat
            from hopaoems.services import wash_repo
            
            logs = wash_repo.list_unwashed_logs()
            grouped = _group_by_vat(logs)
            
            # Assertions
            print(f"  Groups found: {[g['vat_code'] for g in grouped]}")
            self.assertEqual(len(grouped), 2, "Should have exactly 2 groups (C1 and C2)")
            
            # Sort by vat_code for deterministic check
            grouped.sort(key=lambda x: x['vat_code'])
            
            self.assertEqual(grouped[0]['vat_code'], 'C1')
            self.assertEqual(len(grouped[0]['logs']), 2, "C1 should have 2 logs")
            self.assertEqual(float(grouped[0]['logs'][0]['length']), 10.0)
            
            self.assertEqual(grouped[1]['vat_code'], 'C2')
            self.assertEqual(len(grouped[1]['logs']), 1, "C2 should have 1 log")
            self.assertEqual(float(grouped[1]['logs'][0]['length']), 20.0)

if __name__ == "__main__":
    print("GATE: VAT GROUPING BEHAVIOR LOCK")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestVatGroupingBehavior)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if result.wasSuccessful():
        print("  [PASS] Behavioral grouping verified with multi-cylinder dataset")
        sys.exit(0)
    else:
        print("  [FAIL] Grouping behavior failed")
        sys.exit(1)
