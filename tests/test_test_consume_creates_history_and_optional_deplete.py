import os
import sys
import unittest
import tempfile

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from hopaoems import create_app
from hopaoems.services import db, schema_migrations, fabric_repo

class TestTestConsume(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'SECRET_KEY': 'test'
        })
        with self.app.app_context():
            schema_migrations.init_schema()
            self.setup_data()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def setup_data(self):
        db.execute_db("INSERT INTO fabrics (fabric_code) VALUES (?)", ('F1',))
        db.execute_db("INSERT INTO cylinders (fabric_id, cylinder_no) VALUES (?, ?)", (1, 'C1'))
        db.execute_db("INSERT INTO rolls (cylinder_id, roll_no, length_m) VALUES (?, ?, ?)", (1, 'R1', 100))
        db.execute_db("INSERT INTO orders (order_no) VALUES (?)", ('O1',))
        db.execute_db("INSERT INTO samples (sample_no, title) VALUES (?, ?)", ('S1', 'Title 1'))
        db.execute_db("INSERT INTO production_tasks (order_id, fabric_no, sample_id, target_qty) VALUES (?, ?, ?, ?)", (1, 'F1', 1, 50))

    def test_record_test_consume_history(self):
        with self.app.app_context():
            # Consume 10m
            fabric_repo.record_test_consume(1, 10, "Test Note", 1, user_name='test_user')
            
            # Check roll length
            roll = fabric_repo.get_roll(1)
            self.assertEqual(roll['length_m'], 90)
            self.assertEqual(roll['status'], 'in_stock')
            
            # Check history
            history = db.query_db("SELECT * FROM roll_history WHERE roll_id = 1")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]['action'], 'test_consume')
            self.assertEqual(history[0]['new_qty'], 90)
            self.assertEqual(history[0]['source'], 'test_sample')
            self.assertIn("Task=1", history[0]['note'])
            self.assertIn("Fabric=F1", history[0]['note'])

    def test_record_test_consume_clamping(self):
        with self.app.app_context():
            # Current len is 100, try consuming 150
            fabric_repo.record_test_consume(1, 150, "Over consumption", 1, user_name='test_user')
            
            roll = fabric_repo.get_roll(1)
            self.assertEqual(roll['length_m'], 0, "Length should be clamped to 0")
            
            history = db.query_db("SELECT * FROM roll_history WHERE roll_id = 1")
            note = history[0]['note']
            self.assertIn("OVER-CONSUMED/CLAMPED", note)
            self.assertIn("TEST_CONSUME", note)
            self.assertIn("Order=O1", note)
            self.assertIn("Task=1", note)
            self.assertIn("Roll=R1", note)

    def test_record_test_consume_isolation(self):
        with self.app.app_context():
            # Initial logs count
            count_before = db.query_db("SELECT COUNT(*) as c FROM production_logs", one=True)['c']
            
            fabric_repo.record_test_consume(1, 10, "Test Isolation", 1, user_name='test_user')
            
            count_after = db.query_db("SELECT COUNT(*) as c FROM production_logs", one=True)['c']
            self.assertEqual(count_before, count_after, "Production logs count must NOT change")
            
            # Check wash list
            from hopaoems.services import wash_repo
            wash_list = wash_repo.list_unwashed_logs()
            for log in wash_list:
                if log['roll_id'] == 1 and log['length'] == 10:
                    self.fail("Test consume item appeared in wash list!")

if __name__ == "__main__":
    unittest.main()
