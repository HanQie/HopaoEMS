
import sys
import os
import unittest
sys.path.append(os.path.join(os.getcwd(), 'src'))
from src.app_factory import create_app
from src.services import ink_repo
from services.db import get_conn
from werkzeug.security import generate_password_hash

class TestInkCrud(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'WTF_CSRF_ENABLED': False})
        self.client = self.app.test_client()
        self.ensure_test_user()
        self.login()

    def ensure_test_user(self):
         conn = get_conn()
         user = conn.execute("SELECT * FROM users WHERE username = 'test_operator_auto'").fetchone()
         if not user:
             conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                          ('test_operator_auto', generate_password_hash('password123'), 'operator'))
             conn.commit()
         conn.close()

    def login(self):
        self.client.post('/login', data={'username': 'test_operator_auto', 'password': 'password123'}, follow_redirects=True)

    def test_ink_create_update_delete(self):
        # 1. Create - Using correct field names from previous steps
        # Fields: date, type, color, qty, note (name removed/optional in form replacement)
        resp = self.client.post('/ink/new', data={
            'type': 'DyeTest',
            'color': '#FF0000',
            'qty': '10.5',
            'date': '2023-01-01',
            'note': 'Test Note'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        
        # Verify created
        inks = ink_repo.list_inks()
        created_ink = next((i for i in inks if i.get('type') == 'DyeTest'), None)
        self.assertIsNotNone(created_ink, "Ink should be created")
        ink_id = created_ink['id']

        # 2. Update (Edit)
        resp = self.client.post(f'/ink/{ink_id}/edit', data={
            'type': 'PigmentUpdated',
            'color': '#00FF00',
            'qty': '20',
            'date': '2023-01-02',
            'note': 'Updated Note'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        
        updated_ink = ink_repo.get_ink(ink_id)
        self.assertEqual(updated_ink['type'], 'PigmentUpdated')
        self.assertEqual(updated_ink['qty'], 20.0)

        # 3. Delete
        resp = self.client.post(f'/ink/{ink_id}/delete', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        
        # Verify deleted
        deleted_ink = ink_repo.get_ink(ink_id)
        self.assertIsNone(deleted_ink)
        
        print("✅ TestInkCrud: Create -> Edit -> Delete flow passed.")

if __name__ == '__main__':
    unittest.main()
