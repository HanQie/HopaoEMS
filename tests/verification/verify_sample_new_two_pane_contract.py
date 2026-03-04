import os

def verify_sample_new_layout():
    form_path = "src/templates/sample/form.html"
    if not os.path.exists(form_path):
        print(f"❌ {form_path} not found")
        return False
        
    with open(form_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check 1: Hooks
    if 'data-hook="sample-left-pane"' not in content:
        print("❌ Missing data-hook=\"sample-left-pane\"")
        return False
    if 'data-hook="sample-right-pane"' not in content:
        print("❌ Missing data-hook=\"sample-right-pane\"")
        return False
        
    # Check 2: Grid Macro
    if 'C.ui_grid_2col' not in content:
        print("❌ Missing C.ui_grid_2col macro usage")
        return False
        
    print("✅ Sample New Layout Contract verified!")
    return True

if __name__ == "__main__":
    if verify_sample_new_layout():
        exit(0)
    else:
        exit(1)
