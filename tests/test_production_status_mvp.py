
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
import unittest
from app_factory import create_app
from services import production_repo

class TestProductionStatusMVP(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        # Create a dummy production task
        with self.app.app_context():
            payload = {
                'order_id': 1,
                'roll_id': 1,
                'used_length': 50.0,
                'status': 'queued',
                'remark': 'Initial'
            }
            self.task_id = production_repo.create_task(payload)

    def test_viewer_set_status_forbidden(self):
        headers = {"X-Hopao-Role": "viewer"}
        response = self.client.post(f'/production/{self.task_id}/status', 
                                    data={'status': 'hold'}, 
                                    headers=headers)
        self.assertEqual(response.status_code, 403)
        
        # Verify it is still queued
        with self.app.app_context():
            task = production_repo.get_task(self.task_id)
            self.assertEqual(task['status'], 'queued')

    def test_operator_set_status_success(self):
        headers = {"X-Hopao-Role": "operator"}
        for status in ['hold', 'done', 'canceled']:
            response = self.client.post(f'/production/{self.task_id}/status', 
                                        data={'status': status}, 
                                        headers=headers)
            self.assertEqual(response.status_code, 302)
            
            # Verify update
            with self.app.app_context():
                task = production_repo.get_task(self.task_id)
                self.assertEqual(task['status'], status)

    def test_operator_invalid_status_bad_request(self):
        headers = {"X-Hopao-Role": "operator"}
        response = self.client.post(f'/production/{self.task_id}/status', 
                                    data={'status': 'invalid_status'}, 
                                    headers=headers)
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__':
    unittest.main()
