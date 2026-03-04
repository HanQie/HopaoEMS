import unittest
from src.services.db import init_db
from src.services.fabric_repo import create_roll, get_roll, list_rolls

class TestDbFabricRepo(unittest.TestCase):
    def setUp(self):
        # Re-init DB for fresh state
        init_db()

    def test_create_and_get_roll(self):
        payload = {
            'roll_no': 'R-2026-001',
            'fabric_name': 'Cotton 100%',
            'length': 120.5,
            'status': 'in_stock',
            'remark': 'Initial stock'
        }
        
        # Create
        roll_id = create_roll(payload)
        self.assertIsNotNone(roll_id)
        
        # Get
        roll = get_roll(roll_id)
        self.assertIsNotNone(roll)
        self.assertEqual(roll['roll_no'], 'R-2026-001')
        self.assertEqual(roll['fabric_name'], 'Cotton 100%')
        self.assertEqual(roll['length'], 120.5)
        self.assertEqual(roll['status'], 'in_stock')

    def test_list_rolls(self):
        create_roll({'roll_no': 'R1', 'fabric_name': 'F1'})
        create_roll({'roll_no': 'R2', 'fabric_name': 'F2'})
        
        rolls = list_rolls()
        self.assertEqual(len(rolls), 2)
        # Repo sorts by ID DESC
        self.assertEqual(rolls[0]['roll_no'], 'R2')
        self.assertEqual(rolls[1]['roll_no'], 'R1')

if __name__ == '__main__':
    unittest.main()
