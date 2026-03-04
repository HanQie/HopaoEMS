import os
import sys
import unittest

# Setup path
sys.path.append(os.path.abspath('src'))

from services.db import init_db, get_conn
from services import production_repo, fabric_repo, order_repo

class TestFabricStockAdjust(unittest.TestCase):
    def setUp(self):
        self.db_path = 'src/data/test_fabric_adjust_gate.db'
        if os.path.exists(self.db_path): os.remove(self.db_path)
        import services.db
        services.db.DB_PATH = os.path.abspath(self.db_path)
        init_db()
        
        # Setup Data
        fid = fabric_repo.create_fabric("F1", "Cotton", 150, 200)
        cid = fabric_repo.create_cylinder(fid, 'C1')
        self.roll_id = fabric_repo.create_roll(cid, 20, 'R1')
        
    def test_manual_adjustment_logs_history(self):
        print("Verifying fabric stock adjustment contract...")
        
        # Adjust
        fabric_repo.adjust_roll_stock(self.roll_id, 50.5, "Correction")
        
        # Check
        r = fabric_repo.get_roll_with_history(self.roll_id)
        self.assertEqual(r['length_m'], 50.5)
        
        # History
        h = r['history'][0]
        self.assertEqual(h['action'], 'manual_adjust')
        self.assertEqual(h['new_qty'], 50.5)
        self.assertEqual(h['note'], 'Correction')
        
        print("PASSED")

if __name__ == "__main__":
    unittest.main()
