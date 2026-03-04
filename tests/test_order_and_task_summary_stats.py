import unittest
import os
import sys

sys.path.append(os.path.abspath('src'))

from services.db import init_db
from services import order_repo, production_repo, fabric_repo, sample_repo

class TestSummaryStats(unittest.TestCase):
    def setUp(self):
        import services.db
        from pathlib import Path
        self.test_db = Path('test_summary_stats.db')
        if self.test_db.exists():
            try: os.remove(self.test_db)
            except: pass
        services.db.DB_PATH = self.test_db
        init_db()
        
        self.fabric_id = fabric_repo.create_fabric('F001', 'Cotton', 100, 200)
        self.cyl_id = fabric_repo.create_cylinder(self.fabric_id, 'C1')
        self.roll_id = fabric_repo.create_roll(self.cyl_id, 100)
        self.sample1 = sample_repo.create_sample('S1', 'F001')
        self.sample2 = sample_repo.create_sample('S2', 'F001')

    def tearDown(self):
        import gc
        import time
        gc.collect()
        time.sleep(0.1)
        if self.test_db.exists():
            try: os.remove(self.test_db)
            except: pass

    def test_stats_calculation(self):
        print("\nTesting Summary Stats Calculation...")
        
        # 1. Create Order + 2 Tasks
        order_id = order_repo.create_order({'items': [
            {'fabric_no': 'F001', 'sample_id': self.sample1, 'quantity': 100},
            {'fabric_no': 'F001', 'sample_id': self.sample2, 'quantity': 200}
        ]})
        production_repo.sync_tasks_for_order(order_id)
        tasks = production_repo.list_tasks(order_id)
        t1 = tasks[0]['id'] # S2 (DESC order usually)
        t2 = tasks[1]['id'] # S1
        
        # 2. Add Logs
        # Task 1: 1 unwashed log (10m)
        production_repo.add_log_to_task(t1, self.roll_id, 10)
        
        # Task 2: 1 washed log (20m), 1 unwashed log (5m)
        l2 = production_repo.add_log_to_task(t2, self.roll_id, 20)
        production_repo.mark_logs_washed([l2])
        production_repo.add_log_to_task(t2, self.roll_id, 5)
        
        # 3. Mark Task 2 Done (Wait, it has unwashed log 5m, so can't be done yet)
        # Check pre-done stats
        o_stats = production_repo.get_order_summary(order_id)
        self.assertEqual(o_stats['tasks_total'], 2)
        self.assertEqual(o_stats['tasks_done'], 0)
        self.assertEqual(o_stats['unwashed_logs_count'], 2) # 1 from T1, 1 from T2
        self.assertEqual(o_stats['printed_sum_m'], 35.0) # 10 + 20 + 5
        
        # 4. Wash T2's log and complete it
        # Logs for T2: [20(washed), 5(unwashed)]
        # Wash 5m log
        logs_t2 = production_repo.list_logs_by_task(t2)
        unwashed_t2 = [l['id'] for l in logs_t2 if not l['washed_at']]
        production_repo.mark_logs_washed(unwashed_t2)
        production_repo.complete_task(t2)
        
        # 5. Check Order Stats Again
        o_stats = production_repo.get_order_summary(order_id)
        self.assertEqual(o_stats['tasks_done'], 1)
        self.assertEqual(o_stats['unwashed_logs_count'], 1) # Only T1 has 1 unwashed
        self.assertEqual(o_stats['printed_sum_m'], 35.0)
        
        # 6. Check Task Stats (T2)
        t2_stats = production_repo.get_task_summary(t2)
        self.assertEqual(t2_stats['printed_sum_m'], 25.0) # 20 + 5
        self.assertEqual(t2_stats['unwashed_logs_count'], 0)
        self.assertEqual(t2_stats['washed_logs_count'], 2)
        
        print("PASSED: Summary Stats match expected aggregation.")

if __name__ == "__main__":
    unittest.main()
