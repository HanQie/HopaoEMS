
import sys
import os
contract_dir = os.path.dirname(os.path.abspath('src/hopaoems/contracts/smoke_tests.py'))
src_path = os.path.abspath(os.path.join(contract_dir, '..', '..'))
sys.path.insert(0, src_path)
sys.path.append(contract_dir)

import smoke_tests
try:
    success, err = smoke_tests.run_smoke_tests()
    if not success:
        print(f"FAILED: {err}")
    else:
        print("PASSED")
except Exception as e:
    import traceback
    traceback.print_exc()
