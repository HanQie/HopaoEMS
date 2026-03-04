
import unittest
import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from hopaoems.app_factory import create_app
from hopaoems.services.db import get_db

class FunctionalTestCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({'TESTING': True, 'DATABASE': self.db_path})
        self.client = self.app.test_client()
        
        with self.app.app_context():
            from hopaoems.services import schema_migrations
            schema_migrations.init_schema()
            
            # Create Test User
            from hopaoems.services import auth_service, db
            db.execute_db("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                         ('op', auth_service.generate_password_hash('pass'), 'operator'))
                         
    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)
        
    def login(self):
        return self.client.post('/auth/login', data={'username': 'op', 'password': 'pass'}, follow_redirects=True)

    def test_full_flow(self):
        self.login()
        
        # 1. Create Fabric
        rv = self.client.post('/fabric/new', data={
            'fabric_code': 'F001',
            'material': 'Cotton',
            'width_cm': '150',
            'yard_weight_gyd': '250'
        }, follow_redirects=True)
        self.assertIn(b'F001', rv.data)
        
        # Get Fabric ID (assuming 1)
        fabric_id = 1
        
        # 2. Add Cylinder & Roll (Need repo access or UI route? UI Fabric View doesn't have add cylinder form implemented in blueprint!
        # Wait, my blueprint for fabric only had 'new' for fabric. 
        # The prompt didn't strictly require UI for adding cylinders/rolls, but "Fabric Module" implies it.
        # However, checking `ui_fabric.py`, I missed `cylinder_new` and `roll_new` routes!
        # CRITICAL GAP. I need to fix this or use Repo for setup in test if it's acceptable.
        # But "Rebuild: Fabric Module" implies full functionality found in v1?
        # The user strict constraints focused on structure.
        # For a "One-pass Rebuild", basic data entry is expected.
        # I will use Repo to insert data for this test to proceed, noting the gap or fix it.
        # Fixing it is better. I'll patch ui_fabric after this test creation.
        
        with self.app.app_context():
            from hopaoems.services import fabric_repo
            fabric_repo.create_cylinder(fabric_id, 'C-01')
            fabric_repo.create_roll(1, 'R-001', 100.0, 20.0, 'Initial')
            
        # 3. Create Sample
        rv = self.client.post('/sample/new', data={
            'sample_no': 'S001',
            'title': 'Test Sample',
            'fabric_no': 'F001',
            'date_received': '2023-01-01'
        }, follow_redirects=True)
        self.assertIn(b'S001', rv.data)
        
        # 4. Create Order (Trigger Production Task)
        # items[0][fabric_no], etc.
        rv = self.client.post('/order/new', data={
            'order_no': 'ORD-001',
            'received_date': '2023-01-02',
            'items[0][fabric_no]': 'F001',
            'items[0][sample_id]': '1',
            'items[0][qty]': '50',
            'items[0][note]': 'Rush'
        }, follow_redirects=True)
        self.assertIn(b'ORD-001', rv.data)
        
        # Verify Production Task Created
        with self.app.app_context():
            from hopaoems.services import production_repo
            tasks = production_repo.list_active_tasks()
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]['order_no'], 'ORD-001')
            task_id = tasks[0]['id']
            
        # 5. Quick Produce (Deduct Stock, Create Log)
        rv = self.client.post(f'/production/task/{task_id}/produce', data={
            'roll_id': '1', # R-001
            'length': '10',
            'note': 'Print 10m'
        }, follow_redirects=True)
        self.assertIn(b'10.0', rv.data) # Logged length
        
        # Verify Stock Deducted
        with self.app.app_context():
            base_roll = fabric_repo.get_roll(1)
            self.assertEqual(base_roll['length_m'], 90.0)
            
        # 6. Wash Flow
        # List Unwashed
        rv = self.client.get('/wash/')
        self.assertIn(b'ORD-001', rv.data)
        
        # Batch Wash
        # We need log id.
        with self.app.app_context():
            logs = production_repo.list_logs(task_id)
            log_id = logs[0]['id']
            
        rv = self.client.post('/wash/', data={
            'log_ids': [str(log_id)]
        }, follow_redirects=True)
        
        # Verify moved to history
        rv = self.client.get('/wash/history')
        self.assertIn(b'ORD-001', rv.data)
        
        # Verify Task Progress (Washed updated)
        with self.app.app_context():
            task = production_repo.get_task_progress(task_id)
            self.assertEqual(task['washed'], 10.0)

if __name__ == '__main__':
    unittest.main()
