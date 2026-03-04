import os
import sys
sys.path.append(os.path.join(os.getcwd(), 'src'))
from hopaoems import create_app
from hopaoems.services import db, schema_migrations

app = create_app()
with app.app_context():
    print("Seeding test data...")
    # Clean/Init
    # schema_migrations.init_schema()
    
    # Check if we have an operator
    op = db.query_db("SELECT * FROM users WHERE username = 'operator'", one=True)
    if not op:
        print("Creating operator user...")
        from werkzeug.security import generate_password_hash
        db.execute_db("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                      ('operator', generate_password_hash('operator'), 'operator'))
    
    # Create a fabric
    f = db.query_db("SELECT * FROM fabrics WHERE fabric_code = 'F-TEST'", one=True)
    if not f:
        db.execute_db("INSERT INTO fabrics (fabric_code, material) VALUES (?, ?)", ('F-TEST', 'Cotton'))
        f_id = 1 # Assuming first
    else:
        f_id = f['id']
        
    # Create a sample
    s = db.query_db("SELECT * FROM samples WHERE sample_no = 'S-TEST'", one=True)
    if not s:
        db.execute_db("INSERT INTO samples (sample_no, title, preview_path) VALUES (?, ?, ?)", ('S-TEST', 'Test Sample', '/static/test.jpg'))
        s_id = 1
    else:
        s_id = s['id']
        
    # Create an order
    o = db.query_db("SELECT * FROM orders WHERE order_no = 'ORD-TEST'", one=True)
    if not o:
        db.execute_db("INSERT INTO orders (order_no) VALUES (?)", ('ORD-TEST',))
        o_id = 1
    else:
        o_id = o['id']
        
    # Create a cylinder
    cyl = db.query_db("SELECT * FROM cylinders WHERE cylinder_no = 'V-TEST'", one=True)
    if not cyl:
        db.execute_db("INSERT INTO cylinders (fabric_id, cylinder_no) VALUES (?, ?)", (f_id, 'V-TEST'))
        cyl_id = 1
    else:
        cyl_id = cyl['id']
        
    # Create a roll
    roll = db.query_db("SELECT * FROM rolls WHERE roll_no = 'R-TEST'", one=True)
    if not roll:
        db.execute_db("INSERT INTO rolls (cylinder_id, roll_no, length_m) VALUES (?, ?, ?)", (cyl_id, 'R-TEST', 100))
        roll_id = 1
    else:
        roll_id = roll['id']
        
    # Create a task in 'printing' status
    task = db.query_db("SELECT * FROM production_tasks WHERE fabric_no = 'F-TEST'", one=True)
    if not task:
        db.execute_db("INSERT INTO production_tasks (order_id, sample_id, fabric_no, target_qty, status) VALUES (?, ?, ?, ?, ?)",
                      (o_id, s_id, 'F-TEST', 50, 'printing'))
        task_id = 1
    else:
        task_id = task['id']
        
    # Create a log
    log = db.query_db("SELECT * FROM production_logs LIMIT 1", one=True)
    if not log:
        db.execute_db("INSERT INTO production_logs (task_id, roll_id, length, operator_id) VALUES (?, ?, ?, ?)",
                      (task_id, roll_id, 10, 1))
    
    print("Seeding complete.")
