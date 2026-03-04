import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from src.app_factory import create_app
from src.services.db import init_db
from src.services.production_repo import get_task

class TestProductionMVP(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        
        # Init DB
        init_db()
        
        # Reset admin password for login
        from werkzeug.security import generate_password_hash
        from src.services.db import get_conn
        conn = get_conn()
        conn.execute('UPDATE users SET password_hash = ? WHERE username = ?', 
                     (generate_password_hash('admin123'), 'admin'))
        conn.commit()
        conn.close()
    
    def login(self):
        return self.client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

    def test_production_flow(self):
        # Login first
        self.login()
        
        # 1. GET /production (Empty list check)
        resp = self.client.get('/production')
        self.assertEqual(resp.status_code, 200)

        # 2. POST /production/new (Create Task)
        resp = self.client.post('/production/new', data={
            'order_id': 'ORD-123',
            'roll_id': 'ROLL-55',
            'used_length': '25.5',
            'remark': 'Test Task'
        })
        self.assertEqual(resp.status_code, 302)
        # Verify redirect to task view (ID 1)
        
        # Verify task view content
        resp = self.client.get('/production/1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'ORD-123', resp.data)
        self.assertIn(b'ROLL-55', resp.data)
        self.assertIn(b'25.5', resp.data)
        
        # 3. Verify initial state from DB
        task = get_task(1)
        self.assertIsNotNone(task)
        self.assertEqual(task['washed'], 0)
        self.assertEqual(task['status'], 'printing')

        # 4. POST /production/wash-list (Mark as Washed)
        resp = self.client.post('/production/wash-list', data={
            'task_ids': '1'
        })
        self.assertEqual(resp.status_code, 302)
        
        # 5. Verify washed status from DB
        task = get_task(1)
        self.assertEqual(task['washed'], 1)
        self.assertEqual(task['status'], 'washed')

if __name__ == '__main__':
    unittest.main()
