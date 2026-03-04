import os
import sys

# Add hopaoems to path
contract_dir = os.path.dirname(os.path.abspath(__file__))
root_path = os.path.join(contract_dir, '..', '..', '..')
src_path = os.path.join(root_path, 'src')
sys.path.insert(0, src_path)

# Import and run Gate 7
from hopaoems.contracts.run_gates import run_wash_vat_header_asset_gate

success, err = run_wash_vat_header_asset_gate()
if success:
    print("Gate 7 PASSED")
else:
    print(f"Gate 7 FAILED: {err}")
