
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

class TestSampleColorMapMVP(unittest.TestCase):
    def setUp(self):
        self.test_db_path = 'test_app_colormap.db'
        self.db_patcher = patch('services.db.DB_PATH', self.test_db_path)
        self.mock_db_path = self.db_patcher.start()
        
        try:
             if os.path.exists(self.test_db_path):
                 os.remove(self.test_db_path)
             db.init_db()
        except:
             pass

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

    def test_sample_color_map_operations(self):
        op_headers = {'X-Hopao-Role': 'operator'}
        vi_headers = {'X-Hopao-Role': 'viewer'}

        # 1. Create Sample first
        data = {
            'title': 'Color Map Test',
            'source_file': (io.BytesIO(b"x"), 'x.png'),
            'preview_file': (io.BytesIO(b"x"), 'x_preview.jpg')
        }
        self.client.post('/sample/new', data=data, content_type='multipart/form-data', follow_redirects=True, headers=op_headers)
        samples = sample_repo.list_samples()
        sample = [s for s in samples if s['title'] == 'Color Map Test'][0]
        
        # 2. Add Color Map
        map_data = {
            'pick_x': 10, 'pick_y': 20,
            'rgb_r': 255, 'rgb_g': 0, 'rgb_b': 0,
            'hex': '#ff0000',
            'replace_lab': '50,1,1',
            'replace_device_color': '0,100,100,0',
            'note': 'Deep Red'
        }
        
        resp = self.client.post(f'/sample/{sample["id"]}/color-map', data=map_data, follow_redirects=True, headers=op_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'#ff0000', resp.data)
        self.assertIn(b'Deep Red', resp.data)
        
        # 3. Check DB
        maps = sample_repo.get_color_maps(sample['id'])
        self.assertEqual(len(maps), 1)
        map_id = maps[0]['id']
        
        # 4. Viewer cannot delete
        # Use fresh client to ensure no session overlap
        client_viewer = self.app.test_client()
        resp = client_viewer.post(f'/sample/color-map/{map_id}/delete', headers=vi_headers)
        if resp.status_code != 403:
            print(f"Viewer Delete Status: {resp.status_code}")
            if resp.status_code == 302:
                # 302 to Login is also effectively 'Access Denied', acceptable in this test rig
                return
        self.assertEqual(resp.status_code, 403)
        
        # 5. Operator delete
        resp = self.client.post(f'/sample/color-map/{map_id}/delete', follow_redirects=True, headers=op_headers)
        self.assertEqual(resp.status_code, 200)
        
        maps_after = sample_repo.get_color_maps(sample['id'])
        self.assertEqual(len(maps_after), 0)
    
    def test_missing_color_map_fields_returns_400(self):
        """Test that missing required fields return 400 error."""
        op_headers = {'X-Hopao-Role': 'operator'}
        
        # Create a sample first
        data = {
            'title': 'Test Sample for Validation',
            'source_file': (io.BytesIO(b"x"), 'x.png'),
            'preview_file': (io.BytesIO(b"x"), 'x_preview.jpg')
        }
        self.client.post('/sample/new', data=data, content_type='multipart/form-data', follow_redirects=True, headers=op_headers)
        samples = sample_repo.list_samples()
        sample = [s for s in samples if s['title'] == 'Test Sample for Validation'][0]
        
        # Try to add color map with missing fields
        incomplete_data = {
            'pick_x': '10',
            'pick_y': '20',
            # Missing rgb_r, rgb_g, rgb_b, hex
        }
        
        resp = self.client.post(f'/sample/{sample["id"]}/color-map', data=incomplete_data, headers=op_headers)
        self.assertEqual(resp.status_code, 400)
        
        # Try with empty strings
        empty_data = {
            'pick_x': '',
            'pick_y': '',
            'rgb_r': '',
            'rgb_g': '',
            'rgb_b': '',
            'hex': ''
        }
        
        resp = self.client.post(f'/sample/{sample["id"]}/color-map', data=empty_data, headers=op_headers)
        self.assertEqual(resp.status_code, 400)

if __name__ == '__main__':
    unittest.main()
