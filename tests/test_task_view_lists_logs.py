import os
import sys
import unittest
import tempfile

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from hopaoems import create_app
from hopaoems.services import db, schema_migrations

class TestTaskLogsView(unittest.TestCase):
    def setUp(self):
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
        db.execute_db("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", ('operator', 'x', 'operator'))
        db.execute_db("INSERT INTO fabrics (fabric_code) VALUES (?)", ('F1',))
        db.execute_db("INSERT INTO samples (sample_no, title, preview_path) VALUES (?, ?, ?)", ('S1', 'Sample 1', '/static/thumb.jpg'))
        db.execute_db("INSERT INTO cylinders (fabric_id, cylinder_no) VALUES (?, ?)", (1, 'C1'))
        db.execute_db("INSERT INTO rolls (cylinder_id, roll_no, length_m) VALUES (?, ?, ?)", (1, 'R1', 100))
        db.execute_db("INSERT INTO orders (order_no) VALUES (?)", ('O1',))
        db.execute_db("INSERT INTO production_tasks (order_id, fabric_no, sample_id, target_qty) VALUES (?, ?, ?, ?)", (1, 'F1', 1, 50))
        
        # Create a log
        db.execute_db("INSERT INTO production_logs (task_id, roll_id, length, operator_id) VALUES (?, ?, ?, ?)", (1, 1, 10, 1))

    def test_task_view_content(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            
        response = self.client.get('/production/task/1')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        
        # Check for logs table and content
        self.assertIn('Sample 1', html)
        self.assertIn('R1', html)
        self.assertIn('10', html)
        self.assertIn('/static/thumb.jpg', html)
        self.assertIn('Test Consume', html) # Button should be there for operator/viewer? (Operator only based on route but usually visible if printing)

if __name__ == "__main__":
    unittest.main()
