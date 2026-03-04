
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
import unittest
from app_factory import create_app
from services import fabric_repo

class TestFabricDeleteMVP(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        # Create a dummy roll to delete
        with self.app.app_context():
            payload = {
                'roll_no': 'ROLL-DEL',
                'fabric_name': 'Delete Fabric',
                'length': '100',
                'status': 'in_stock',
                'remark': 'Delete me'
            }
            self.roll_id = fabric_repo.create_roll(payload)

    def test_viewer_delete_forbidden(self):
        headers = {"X-Hopao-Role": "viewer"}
        response = self.client.post(f'/fabric/rolls/{self.roll_id}/delete', headers=headers)
        self.assertEqual(response.status_code, 403)
        
        with self.app.app_context():
            roll = fabric_repo.get_roll(self.roll_id)
            self.assertIsNotNone(roll)

    def test_operator_delete_success(self):
        headers = {"X-Hopao-Role": "operator"}
        response = self.client.post(f'/fabric/rolls/{self.roll_id}/delete', headers=headers)
        self.assertIn(response.status_code, [302, 303])
        
        with self.app.app_context():
            roll = fabric_repo.get_roll(self.roll_id)
            self.assertIsNone(roll)

if __name__ == '__main__':
    unittest.main()
