
import sys
sys.path.insert(0, 'src')

from hopaoems.app_factory import create_app
from hopaoems.services import sample_repo, db

app = create_app()

with app.app_context():
    print("--- Testing Sample ID Handling ---")
    
    # 1. List samples to see what IDs exist
    samples = sample_repo.list_samples()
    print(f"List returned {len(samples)} samples")
    
    if not samples:
        print("No samples found. Creating one...")
        # Create a dummy sample
        new_id = sample_repo.create_sample(
            sample_no='TEST-001',
            title='Test Sample',
            fabric_no='F-001'
        )
        print(f"Created sample with ID: {new_id} (type: {type(new_id)})")
        samples = sample_repo.list_samples()
        
    if samples:
        first = samples[0]
        # Check ID type in row
        # sqlite3.Row supports key access or iteration. Convert to dict to see.
        first_dict = dict(first)
        print(f"First sample row: {first_dict}")
        
        pk = first['id']
        print(f"ID from list: {pk} (type: {type(pk)})")
        
        # 2. Try get_sample with this ID
        print(f"Calling get_sample({pk})...")
        res = sample_repo.get_sample(pk)
        print(f"Result: {dict(res) if res else 'None'}")
        
        # 3. Try get_sample with string ID if it was int
        if isinstance(pk, int):
            print(f"Calling get_sample('{pk}') (string)...")
            res_str = sample_repo.get_sample(str(pk))
            print(f"Result (str): {dict(res_str) if res_str else 'None'}")
            
    print("--- Done ---")
