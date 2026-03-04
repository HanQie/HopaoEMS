import os
import json
import unittest
from pathlib import Path
from src.app_factory import create_app
from src.services.db import init_db
from src.services.fabric_repo import get_roll

class TestFabricMVP(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Init DB
        init_db()
        
        # Clean JSON for fallback safety check
        self.data_file = Path('src/data/fabric_rolls.json')
        self.original_content = None
        if self.data_file.exists():
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.original_content = f.read()
        
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump([], f)

    def tearDown(self):
        if self.original_content is not None:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                f.write(self.original_content)
        elif self.data_file.exists():
            os.remove(self.data_file)

    def test_fabric_flow_db(self):
        # 1. Empty list
        resp = self.client.get('/fabric/rolls')
        self.assertEqual(resp.status_code, 200)

        # 2. POST /fabric/rolls/new
        resp = self.client.post('/fabric/rolls/new', data={
            'roll_no': 'DB-ROLL-01',
            'fabric_name': 'DB Fabric',
            'length': '150.0',
            'status': 'in_stock',
            'remark': 'DB Remark'
        })
        self.assertEqual(resp.status_code, 302)
        # Assumed ID 1
        
        # 3. GET /fabric/rolls/1
        resp = self.client.get('/fabric/rolls/1')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'DB-ROLL-01', resp.data)
        
        # 4. Check DB directly
        roll = get_roll(1)
        self.assertIsNotNone(roll)
        self.assertEqual(roll['roll_no'], 'DB-ROLL-01')
        self.assertEqual(roll['fabric_name'], 'DB Fabric')
        self.assertEqual(roll['length'], 150.0)

if __name__ == '__main__':
    unittest.main()
