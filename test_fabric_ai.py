import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from hopaoems.app_factory import create_app
from hopaoems.ai_engine.tools import _exec_delete_fabric, _exec_partial_stock_in, ToolContext
from hopaoems.services.db import query_db, execute_db

app = create_app()

class MockProcessor:
    pass

class MockContext(ToolContext):
    def __init__(self, db_path, lang="zh", username="operator"):
        super().__init__(db_path, lang, username, MockProcessor())

def test_delete_fabric():
    with app.app_context():
        ctx = MockContext(db_path="test.db")
        
        # We know "TEST_EMPTY_01" and "TEST_DUP_01" exist from the previous runs.
        # Let's delete them.
        res1 = _exec_delete_fabric({"fabric_code": "TEST_EMPTY_01"}, ctx)
        print("Delete TEST_EMPTY_01:", res1)
        
        res2 = _exec_delete_fabric({"fabric_code": "TEST_DUP_01"}, ctx)
        print("Delete TEST_DUP_01:", res2)
        
        # Verify db
        f1 = query_db("SELECT id FROM fabrics WHERE fabric_code = 'TEST_EMPTY_01'", one=True)
        f2 = query_db("SELECT id FROM fabrics WHERE fabric_code = 'TEST_DUP_01'", one=True)
        print("TEST_EMPTY_01 in DB:", f1 is not None)
        print("TEST_DUP_01 in DB:", f2 is not None)
        
        assert f1 is None
        assert f2 is None
        
        print("ALL TESTS PASSED!")

if __name__ == "__main__":
    test_delete_fabric()
