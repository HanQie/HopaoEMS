import os
import json
import unittest
from pathlib import Path
from src.app_factory import create_app

class TestFabricBackend(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Path to fabric_rolls.json
        self.data_file = Path('src/data/fabric_rolls.json')
        
        # Backup existing data
        self.original_content = None
        if self.data_file.exists():
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.original_content = f.read()
        
        # Ensure fresh empty list
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump([], f)

    def tearDown(self):
        # Restore original content
        if self.original_content is not None:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                f.write(self.original_content)
        elif self.data_file.exists():
            os.remove(self.data_file)

    def test_fabric_roll_creation_flow(self):
        # 1. POST /fabric/rolls/new
        data = {
            'roll_no': 'FR-2026-001',
            'fabric_name': 'Cotton Canvas',
            'length': '50',
            'status': 'in_stock',
            'remark': 'Initial stock'
        }
        resp = self.client.post('/fabric/rolls/new', data=data)
        
        # 2. Check redirect to /fabric/rolls/1
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.location.endswith('/fabric/rolls/1'))
        
        # 3. Check if JSON data is saved
        with open(self.data_file, 'r', encoding='utf-8') as f:
            rolls = json.load(f)
            self.assertEqual(len(rolls), 1)
            self.assertEqual(rolls[0]['roll_no'], 'FR-2026-001')
            self.assertEqual(rolls[0]['fabric_name'], 'Cotton Canvas')

        # 4. GET /fabric/rolls/1
        resp = self.client.get('/fabric/rolls/1')
        self.assertEqual(resp.status_code, 200)

if __name__ == '__main__':
    unittest.main()
