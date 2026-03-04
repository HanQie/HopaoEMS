from hopaoems.services.db import execute_db, commit
from hopaoems.services import fabric_repo
import os

def reset():
    tables = [
        'production_logs',
        'roll_history',
        'rolls',
        'cylinders',
        'fabrics'
    ]
    print('Cleaning up Fabric module data...')
    for table in tables:
        try:
            execute_db(f'DELETE FROM {table}')
            print(f'  Cleared {table}')
        except Exception as e:
            print(f'  Failed to clear {table}: {e}')
    
    try:
        execute_db("DELETE FROM sqlite_sequence WHERE name IN ('fabrics', 'cylinders', 'rolls')")
    except Exception as e:
        print(f"  Failed to reset sequences: {e}")
    commit()
    print('Cleanup complete.')

def seed():
    print('Seeding fake data...')
    # 1. Fabrics
    f1 = fabric_repo.create_fabric('F-POLY-TOP', width_mm=1500, gram_per_yard=200, material_type='poly')
    f2 = fabric_repo.create_fabric('F-NYLON-PRO', width_mm=1600, gram_per_yard=220, material_type='nylon')
    f3 = fabric_repo.create_fabric('F-MESH-AIR', width_mm=1700, gram_per_yard=180, material_type='other')
    f4 = fabric_repo.create_fabric('F-DRY-FIT', width_mm=1500, gram_per_yard=150, material_type='poly')
    print(f"  Created 4 Fabrics.")

    # 2. Cylinders
    c1_id = fabric_repo.create_cylinder(f1['id'], 'CYL-101')
    c2_id = fabric_repo.create_cylinder(f1['id'], 'CYL-102')
    c3_id = fabric_repo.create_cylinder(f2['id'], 'CYL-201')
    c4_id = fabric_repo.create_cylinder(f3['id'], 'CYL-301')
    c5_id = fabric_repo.create_cylinder(f4['id'], 'CYL-401')
    c6_id = fabric_repo.create_cylinder(f4['id'], 'CYL-402')
    print(f"  Created 6 Cylinders.")

    # 3. Rolls
    # CYL-101 (F1)
    fabric_repo.create_roll(c1_id, 'ROLL-001', 100.0, 20.0, 'Initial seed')
    fabric_repo.create_roll(c1_id, 'ROLL-002', 150.0, 30.0, 'Batch A')
    # CYL-102 (F1)
    fabric_repo.create_roll(c2_id, 'ROLL-003', 80.0, 16.0, 'Small roll')
    # CYL-201 (F2)
    fabric_repo.create_roll(c3_id, 'ROLL-004', 200.0, 44.0, 'Heavy nylon')
    fabric_repo.create_roll(c3_id, 'ROLL-005', 180.0, 40.0, 'Legacy NY')
    # CYL-301 (F3)
    fabric_repo.create_roll(c4_id, 'ROLL-006', 300.0, 54.0, 'Air mesh block')
    # CYL-401 (F4)
    fabric_repo.create_roll(c5_id, 'ROLL-007', 120.0, 18.0, 'Dry fit start')
    # CYL-402 (F4)
    fabric_repo.create_roll(c6_id, 'ROLL-008', 50.0, 7.5, 'Sample roll')
    
    # Mark some as depleted for testing
    execute_db("UPDATE rolls SET status = 'depleted' WHERE roll_no IN ('ROLL-002', 'ROLL-005')")
    
    print(f"  Created 8 Rolls (2 depleted).")

    commit()
    print('Seeding complete.')

if __name__ == '__main__':
    from hopaoems.app_factory import create_app
    app = create_app()
    with app.app_context():
        reset()
        seed()
