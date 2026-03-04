import unittest
import sqlite3
import tempfile
import shutil
from pathlib import Path

class TestMigrations(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test database
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / 'test.db'
        
        # Monkey-patch the DB_PATH in db module
        import src.services.db as db_module
        self.original_db_path = db_module.DB_PATH
        db_module.DB_PATH = self.test_db_path
    
    def tearDown(self):
        # Restore original DB_PATH
        import src.services.db as db_module
        db_module.DB_PATH = self.original_db_path
        
        # Clean up temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_migrations_idempotent(self):
        """Test that running init_db() twice doesn't cause errors or duplicate migrations."""
        from src.services.db import init_db, get_conn
        
        # First run - should apply all migrations
        init_db()
        
        # Check that migrations were applied
        conn = get_conn()
        cursor = conn.cursor()
        
        # Verify schema_migrations exists
        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchall()
        self.assertEqual(len(tables), 1, "schema_migrations table should exist")
        
        # Get count of applied migrations
        first_run_count = cursor.execute(
            "SELECT COUNT(*) as count FROM schema_migrations"
        ).fetchone()['count']
        self.assertGreater(first_run_count, 0, "At least one migration should be applied")
        
        # Verify actual tables were created
        all_tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t['name'] for t in all_tables]
        
        # Should have at least: schema_migrations, orders, order_items, samples, fabric_rolls, production_tasks
        self.assertIn('schema_migrations', table_names)
        self.assertIn('orders', table_names)
        self.assertIn('samples', table_names)
        
        conn.close()
        
        # Second run - should NOT re-apply migrations
        init_db()
        
        # Check that no duplicate migrations were applied
        conn = get_conn()
        cursor = conn.cursor()
        
        second_run_count = cursor.execute(
            "SELECT COUNT(*) as count FROM schema_migrations"
        ).fetchone()['count']
        
        self.assertEqual(
            first_run_count, 
            second_run_count,
            "Second init_db() should not re-apply migrations"
        )
        
        # Verify no errors occurred (we got here without exceptions)
        conn.close()

if __name__ == '__main__':
    unittest.main()
