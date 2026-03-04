import unittest
import os
from src.services.db import init_db
from src.services.order_repo import create_order, get_order, list_orders

class TestDbOrderRepo(unittest.TestCase):
    def setUp(self):
        # Re-init DB for fresh state
        init_db()

    def test_create_and_get_order(self):
        payload = {
            'customer_name': 'Test Corp',
            'order_date': '2026-01-01',
            'remark': 'Urgent Order',
            'items': [
                {'item': 'Widget A', 'quantity': 10, 'price': 5.0},
                {'item': 'Widget B', 'quantity': 2, 'price': 100.0}
            ]
        }
        
        # Create
        order_id = create_order(payload)
        self.assertIsNotNone(order_id)
        
        # Get
        order = get_order(order_id)
        self.assertIsNotNone(order)
        self.assertEqual(order['customer_name'], 'Test Corp')
        self.assertEqual(order['status'], 'pending')
        self.assertEqual(len(order['items']), 2)
        
        item_names = [i['item'] for i in order['items']]
        self.assertIn('Widget A', item_names)
        self.assertIn('Widget B', item_names)

    def test_list_orders(self):
        create_order({'customer_name': 'C1', 'order_date': '2026-01-01'})
        create_order({'customer_name': 'C2', 'order_date': '2026-01-02'})
        
        orders = list_orders()
        self.assertEqual(len(orders), 2)
        # Check order (repo sorts by ID DESC)
        self.assertEqual(orders[0]['customer_name'], 'C2')
        self.assertEqual(orders[1]['customer_name'], 'C1')

if __name__ == '__main__':
    unittest.main()
