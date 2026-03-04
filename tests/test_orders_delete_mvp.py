
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
import unittest
from app_factory import create_app
from services import order_repo

class TestOrdersDeleteMVP(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        # Create a dummy order to delete
        with self.app.app_context():
            payload = {
                'customer_name': 'To Be Deleted',
                'order_date': '2025-01-01',
                'remark': 'Delete me',
                'items': []
            }
            self.order_id = order_repo.create_order(payload)

    def test_viewer_delete_forbidden(self):
        headers = {"X-Hopao-Role": "viewer"}
        response = self.client.post(f'/order/{self.order_id}/delete', headers=headers)
        # Viewer should be 403
        self.assertEqual(response.status_code, 403)
        
        # Verify it still exists
        with self.app.app_context():
            order = order_repo.get_order(self.order_id)
            self.assertIsNotNone(order)

    def test_operator_delete_success(self):
        headers = {"X-Hopao-Role": "operator"}
        response = self.client.post(f'/order/{self.order_id}/delete', headers=headers)
        # Operator should be 302 (redirect after success)
        self.assertIn(response.status_code, [302, 303])
        
        # Verify it is gone
        with self.app.app_context():
            order = order_repo.get_order(self.order_id)
            self.assertIsNone(order)

if __name__ == '__main__':
    unittest.main()
