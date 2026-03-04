import unittest
import os
import sys
from flask import url_for

# Add src to path
sys.path.append(os.path.abspath('src'))

from app_factory import create_app
from services.db import init_db, get_conn
from services import order_repo, fabric_repo, sample_repo

class TestOrderCRUDMinimal(unittest.TestCase):
    def setUp(self):
        # Use a temporary test database
        self.db_path = 'src/data/test_app_crud.db'
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        # Override DB_PATH in services.db
        import services.db
        services.db.DB_PATH = os.path.abspath(self.db_path)
        
        init_db()
        
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test"})
        self.client = self.app.test_client()
        
        # Seeds for testing
        self.fabric_id = fabric_repo.create_fabric("F001", "Cotton", 150, 200)
        self.sample_id = sample_repo.create_sample(
            sample_no="S999", 
            name="Test Sample Label", # Added name for label check
            fabric_no="F001"
        )

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except:
                pass

    def test_order_full_lifecycle(self):
        """Verify Create -> View (Label) -> Edit -> Update cycle."""
        
        # 1. CREATE
        order_data = {
            'order_no': 'ORD-INIT',
            'received_date': '2026-01-28',
            'due_date': '2026-02-15',
            'note': 'Initial note.',
            'fabric_no[]': ['F001'],
            'sample_id[]': [str(self.sample_id)],
            'qty[]': ['100'],
            'note[]': ['Item 1']
        }
        
        response = self.client.post('/order/new', data=order_data, headers={"X-Hopao-Role": "operator"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('ORD-INIT', response.get_data(as_text=True))
        # Check if Sample Label is shown instead of ID
        self.assertIn('Test Sample Label', response.get_data(as_text=True))
        
        order_id = order_repo.list_orders()[0]['id']
        
        # 2. EDIT (GET)
        response = self.client.get(f'/order/edit/{order_id}', headers={"X-Hopao-Role": "operator"})
        self.assertEqual(response.status_code, 200)
        self.assertIn('ORD-INIT', response.get_data(as_text=True))
        
        # 3. UPDATE (POST)
        update_data = {
            'order_no': 'ORD-UPDATED',
            'received_date': '2026-01-29',
            'due_date': '2026-02-20',
            'note': 'Updated note.',
            'fabric_no[]': ['F001', 'F001'],
            'sample_id[]': [str(self.sample_id), ''],
            'qty[]': ['200', '50'],
            'note[]': ['Updated Item 1', 'New Item 2']
        }
        
        response = self.client.post(f'/order/edit/{order_id}', data=update_data, headers={"X-Hopao-Role": "operator"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify in DB
        order = order_repo.get_order(order_id)
        self.assertEqual(order['order_no'], 'ORD-UPDATED')
        self.assertEqual(order['note'], 'Updated note.')
        self.assertEqual(len(order['items']), 2)
        self.assertEqual(order['items'][0]['qty'], 200.0)
        self.assertEqual(order['items'][1]['note'], 'New Item 2')
        
        # 4. VIEWER PERMISSION CHECK
        # Viewer should be able to view but NOT edit/delete
        # GET /order/edit/<id> for viewer should be 403 or redirect depending on check_write_permission implementation
        # Actually, check_write_permission in ui.py usually aborts(403)
        response = self.client.get(f'/order/edit/{order_id}', headers={"X-Hopao-Role": "viewer"})
        self.assertEqual(response.status_code, 403)

if __name__ == '__main__':
    unittest.main()
