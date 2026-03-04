import unittest
import os
import json
from pathlib import Path
from src.app_factory import create_app
from src.services.db import init_db
from src.services.order_repo import get_order

class TestOrderMVP(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Init DB (in-file if path is standard, or maybe test DB?)
        # Default config points to app.db. init_db() clears/creates it?
        # init_db() in services/db.py uses SCHEMA_PATH and DB_PATH relative to file.
        # It references 'data/app.db'.
        # Since this is a test, ideally we use a test DB, but for MVP Step 2, let's use the real one/file logic 
        # provided by user: "新增 test_order_mvp.py：先呼叫 init_db()"
        init_db()

    def test_order_flow_db(self):
        # 1. Empty list
        resp = self.client.get('/order')
        self.assertEqual(resp.status_code, 200)

        # 2. POST /order/new
        resp = self.client.post('/order/new', data={
            'customer_name': 'DB Customer',
            'order_date': '2026-02-01',
            'item[]': ['Item DB'],
            'quantity[]': ['5'],
            'price[]': ['50.0']
        })
        self.assertEqual(resp.status_code, 302)
        # Assuming ID starts at 1
        
        # 3. Verify in View (Routes)
        resp = self.client.get('/order/1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'DB Customer', resp.data)

        # 4. Verify in DB directly (Repo)
        order = get_order(1)
        self.assertIsNotNone(order, "Order not found in DB via repo")
        self.assertEqual(order['customer_name'], 'DB Customer')
        self.assertEqual(order['items'][0]['item'], 'Item DB')

if __name__ == '__main__':
    unittest.main()
