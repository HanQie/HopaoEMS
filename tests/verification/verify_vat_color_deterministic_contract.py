import sys
import os

# Set path for imports
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

try:
    from hopaoems.services import ui_utils
except ImportError:
    print("  [FAIL] Could not import ui_utils")
    sys.exit(1)

def main():
    print("GATE: VAT COLOR DETERMINISTIC CONTRACT")
    
    test_vats = ["VAT001", "VAT002", "BATCH_A", "BATCH_A", "12345"]
    results = {}
    
    for v in test_vats:
        idx = ui_utils.get_vat_tone_idx(v)
        if v in results:
            if results[v] != idx:
                print(f"  [FAIL] Non-deterministic! {v} got {results[v]} then {idx}")
                sys.exit(1)
        else:
            results[v] = idx
        
        # Range check 0-15
        if not (0 <= idx < 16):
            print(f"  [FAIL] {v} tone_idx {idx} out of range (0-15)")
            sys.exit(1)
            
    print(f"  [PASS] {len(test_vats)} checks passed. Deterministic and in range.")
    print(f"  Sample: VAT001 -> {results['VAT001']}, BATCH_A -> {results['BATCH_A']}")
    sys.exit(0)

if __name__ == "__main__":
    main()
