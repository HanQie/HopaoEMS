
import unittest
import io
import os
import sys
import sqlite3
from unittest.mock import patch
from werkzeug.security import generate_password_hash

# Add project root to path
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from app_factory import create_app
from services import sample_repo, db

class TestSampleMVP(unittest.TestCase):
    def setUp(self):
        self.test_db_path = 'test_app.db'
        self.db_patcher = patch('services.db.DB_PATH', self.test_db_path)
        self.mock_db_path = self.db_patcher.start()
        
        try:
             if os.path.exists(self.test_db_path):
                 os.remove(self.test_db_path)
             db.init_db()
        except Exception as e:
             print(f"DB Init failed: {e}")
        
        self.app = create_app({'TESTING': True, 'LOGIN_DISABLED': False, 'WTF_CSRF_ENABLED': False})
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()
        self.db_patcher.stop()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except:
                pass

    def test_operator_create_upload_success(self):
        # Create Mock File
        data = {
            'title': 'Test Sample MVP',
            'remark': 'Remark MVP',
            'source_file': (io.BytesIO(b"fake data"), 'test.tif'),
            'preview_file': (io.BytesIO(b"fake jpg"), 'preview.jpg')
        }
        
        # Use Header Auth
        headers = {'X-Hopao-Role': 'operator'}
        
        response = self.client.post('/sample/new', data=data, follow_redirects=True, 
                                   content_type='multipart/form-data',
                                   headers=headers)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Sample MVP', response.data)
        
        # Check DB
        samples = sample_repo.list_samples()
        found = [s for s in samples if s['title'] == 'Test Sample MVP']
        self.assertEqual(len(found), 1)
        
        # Check View Render
        s_id = found[0]['id']
        resp_view = self.client.get(f'/sample/{s_id}', headers=headers)
        self.assertIn(b'Test Sample MVP', resp_view.data)
        self.assertTrue(b'canvas' in resp_view.data or b'img' in resp_view.data)

    def test_viewer_permission(self):
        headers = {'X-Hopao-Role': 'viewer'}
        
        resp = self.client.get('/sample/new', headers=headers)
        self.assertEqual(resp.status_code, 403)
        
        resp = self.client.post('/sample/new', data={}, headers=headers)
        self.assertEqual(resp.status_code, 403)

if __name__ == '__main__':
    unittest.main()
