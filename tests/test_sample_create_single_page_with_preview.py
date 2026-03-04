
import unittest
import io
import os
import sys
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from app_factory import create_app
from services import sample_repo, db

class TestSampleCreateSinglePageWithPreview(unittest.TestCase):
    def setUp(self):
        self.test_db_path = 'test_app_single_page.db'
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

    def test_single_page_create_with_preview(self):
        """Test complete single-page create flow with temp upload."""
        op_headers = {'X-Hopao-Role': 'operator'}
        
        # Step 1: Upload temp preview
        preview_blob = io.BytesIO(b"fake jpeg data")
        preview_data = {'preview_file': (preview_blob, 'preview.jpg')}
        
        resp = self.client.post('/sample/upload-temp', data=preview_data, content_type='multipart/form-data', headers=op_headers)
        self.assertEqual(resp.status_code, 200)
        
        result = resp.get_json()
        self.assertIn('temp_id', result)
        self.assertIn('preview_url', result)
        
        temp_id = result['temp_id']
        preview_url = result['preview_url']
        
        # Step 2: Verify preview URL is accessible
        resp_preview = self.client.get(preview_url, headers=op_headers)
        self.assertEqual(resp_preview.status_code, 200)
        # Should be image type
        self.assertTrue(resp_preview.content_type.startswith('image/') or resp_preview.content_type == 'application/octet-stream')
        
        # Step 3: Create sample with temp_id
        form_data = {
            'name': 'Test Sample Single Page',
            'title': 'Test Title',
            'fabric_no': 'F001',
            'version': 'V1',
            'temp_id': temp_id
        }
        
        resp_create = self.client.post('/sample/new', data=form_data, follow_redirects=False, headers=op_headers)
        self.assertEqual(resp_create.status_code, 302)  # Redirect to view page
        
        # Extract sample ID from redirect
        location = resp_create.headers.get('Location')
        self.assertIsNotNone(location)
        sample_id = location.split('/')[-1]
        
        # Step 4: GET view page should show preview
        resp_view = self.client.get(f'/sample/{sample_id}', headers=op_headers)
        self.assertEqual(resp_view.status_code, 200)
        self.assertIn(b'Test Sample Single Page', resp_view.data)
        
        # Step 5: Verify preview is in DB and accessible
        sample = sample_repo.get_sample(int(sample_id))
        self.assertIsNotNone(sample)
        self.assertIsNotNone(sample['preview_path'])
        
        # Preview should be moved from temp to final
        # Check that final preview is accessible
        if sample['preview_path']:
            import os.path
            final_preview_exists = os.path.exists(sample['preview_path'])
            self.assertTrue(final_preview_exists, "Final preview file should exist")

if __name__ == '__main__':
    unittest.main()
