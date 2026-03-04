import os
import json
import unittest
from pathlib import Path
from src.app_factory import create_app

class TestProductionBackend(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Path to production_tasks.json matching the app
        self.data_file = Path('src/data/production_tasks.json')
        
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

    def test_production_task_creation(self):
        # 1. POST /production/new
        data = {
            'order_id': '101',
            'roll_id': '50',
            'used_length': '20.5',
            'remark': 'Urgent'
        }
        resp = self.client.post('/production/new', data=data)
        
        # 2. Check redirect and creation
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.location.endswith('/production/1'))
        
        with open(self.data_file, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]['order_id'], '101')
            self.assertEqual(tasks[0]['status'], 'printing')
            self.assertFalse(tasks[0]['washed']) # default

        # 3. GET /production/1
        resp = self.client.get('/production/1')
        self.assertEqual(resp.status_code, 200)

    def test_production_wash_update(self):
        # Create a task manually first
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump([{
                "id": 1,
                "order_id": "101",
                "status": "printing",
                "washed": False
            }], f)
            
        # POST /production/wash-list with task_ids=1
        resp = self.client.post('/production/wash-list', data={'task_ids': '1'})
        
        # Check redirect
        self.assertEqual(resp.status_code, 302)
        
        # Check if updated
        with open(self.data_file, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
            self.assertTrue(tasks[0]['washed'])
            self.assertEqual(tasks[0]['status'], 'washed')

if __name__ == '__main__':
    unittest.main()
