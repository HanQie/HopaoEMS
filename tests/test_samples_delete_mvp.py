
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
import unittest
from app_factory import create_app
from services import sample_repo

class TestSamplesDeleteMVP(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        # Create a dummy sample to delete
        with self.app.app_context():
            payload = {
                'name': 'Sample To Delete',
                'code': 'DEL-101',
                'description': 'Delete me',
                'image_url': ''
            }
            self.sample_id = sample_repo.create_sample(payload)

    def test_viewer_delete_forbidden(self):
        headers = {"X-Hopao-Role": "viewer"}
        response = self.client.post(f'/sample/{self.sample_id}/delete', headers=headers)
        self.assertEqual(response.status_code, 403)
        
        with self.app.app_context():
            sample = sample_repo.get_sample(self.sample_id)
            self.assertIsNotNone(sample)

    def test_operator_delete_success(self):
        headers = {"X-Hopao-Role": "operator"}
        response = self.client.post(f'/sample/{self.sample_id}/delete', headers=headers)
        self.assertIn(response.status_code, [302, 303])
        
        with self.app.app_context():
            sample = sample_repo.get_sample(self.sample_id)
            self.assertIsNone(sample)

if __name__ == '__main__':
    unittest.main()
