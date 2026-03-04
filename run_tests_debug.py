import sys
import traceback
sys.path.insert(0, 'src')
from hopaoems.contracts.smoke_tests import run_smoke_tests

try:
    success, msg = run_smoke_tests()
    if not success:
        print("FAILED:", msg)
except Exception as e:
    traceback.print_exc()
