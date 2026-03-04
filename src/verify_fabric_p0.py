import os
import sys
import unittest
from hopaoems.app_factory import create_app
from hopaoems.services.db import query_db, execute_db, commit
from werkzeug.security import generate_password_hash

class FabricP0Verification(unittest.TestCase):
    def setUp(self):
        self.db_path = 'test_fabric_p0.sqlite'
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except:
                pass
            
        self.app = create_app({'TESTING': True, 'DATABASE': self.db_path, 'WTF_CSRF_ENABLED': False})
        self.client = self.app.test_client()
        with self.app.app_context():
            from hopaoems.services import schema_migrations
            schema_migrations.init_schema()
            
            # Setup fresh data for this test
            execute_db("INSERT INTO fabrics (id, fabric_code, yard_weight_gyd) VALUES (1, 'F-TEST', 200)")
            execute_db("INSERT INTO cylinders (id, fabric_id, cylinder_no) VALUES (1, 1, 'C-TEST')")
            execute_db("INSERT INTO rolls (id, cylinder_id, roll_no, length_m, status) VALUES (1, 1, 'R-TEST', 100, 'in_stock')")
            commit()

            # Ensure admin user exists with known password
            execute_db("INSERT OR REPLACE INTO users (username, password_hash, role) VALUES ('admin', ?, 'operator')", (generate_password_hash('admin'),))
            commit()

            # Login as admin
            res = self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=True)
            if res.status_code != 200:
                 print(f"DEBUG: Login failed in setUp, status {res.status_code}")

    def tearDown(self):
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except:
                pass

    def test_explorer_actions_presence(self):
        """Verify actions exist for operator on in_stock rolls"""
        res = self.client.get('/fabric/explorer?fabric_id=1&cylinder_id=1')
        html = res.get_data(as_text=True)
        try:
            # Check for substrings that should be in our new macro-based layout
            self.assertIn('adjust-stock', html)
            self.assertIn('deplete', html)
            self.assertIn('delete', html)
        except AssertionError as e:
            print(f"DEBUG: Actions presence failed. HTML length: {len(html)}")
            with open('debug_explorer.html', 'w', encoding='utf-8') as f:
                f.write(html)
            if 'admin' in html:
                print("DEBUG: 'admin' found in HTML (User seems logged in)")
            else:
                print("DEBUG: 'admin' NOT found in HTML (User NOT logged in?)")
            raise e
        print("Presence Check: PASS")

    def test_roll_adjust_stock(self):
        """Verify Adjust Stock keeps roll in_stock and updates qty"""
        # GET form
        res = self.client.get('/fabric/roll/1/adjust-stock')
        self.assertEqual(res.status_code, 200)
        
        # POST adjust
        res = self.client.post('/fabric/roll/1/adjust-stock', data={
            'new_length_m': 120,
            'note': 'Test adjustment'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        with self.app.app_context():
            roll = query_db("SELECT * FROM rolls WHERE id = 1", one=True)
            self.assertEqual(roll['length_m'], 120)
            self.assertEqual(roll['status'], 'in_stock')
        print("Roll Adjust: PASS")

    def test_roll_deplete(self):
        """Verify Deplete marks roll as depleted"""
        res = self.client.post('/fabric/roll/1/deplete', follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertEqual(res.status_code, 200)
        
        with self.app.app_context():
            roll = query_db("SELECT * FROM rolls WHERE id = 1", one=True)
            try:
                self.assertEqual(roll['status'], 'depleted')
            except AssertionError as e:
                print(f"DEBUG: Deplete failed. Roll status: {roll['status']}")
                if 'text-rose-700' in html or 'bg-rose-50' in html:
                     print("DEBUG: Found RED alert in HTML (likely error)")
                if 'admin' in html:
                     print("DEBUG: User 'admin' is still in HTML")
                raise e
        print("Roll Deplete: PASS")

    def test_roll_delete_safe(self):
        """Verify Delete works if no production logs exist"""
        # GET confirm
        res = self.client.get('/fabric/roll/1/delete')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Are you sure', res.get_data(as_text=True))
        
        # POST delete
        res = self.client.post('/fabric/roll/1/delete', data={'fabric_id': 1, 'cylinder_id': 1}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        with self.app.app_context():
            roll = query_db("SELECT * FROM rolls WHERE id = 1", one=True)
            if roll:
                 print(f"DEBUG: Delete failed. Roll STILL EXISTS: {roll}")
            self.assertIsNone(roll)
        print("Roll Delete (Safe): PASS")

    def test_fabric_new_and_stock_in(self):
        """Verify Add Fabric flow back to Stock-In"""
        # 1. Add Fabric
        res = self.client.post('/fabric/new?next=/fabric/stock-in', data={
            'fabric_code': 'F-NEW-001',
            'width_mm': '1550',
            'gram_per_yard': '210',
            'material_type': 'nylon'
        })
        # Should redirect to stock-in with fabric_id
        self.assertIn('/fabric/stock-in', res.location)
        self.assertIn('fabric_id=', res.location)
        print("Add Fabric Flow: PASS")

if __name__ == '__main__':
    unittest.main()
