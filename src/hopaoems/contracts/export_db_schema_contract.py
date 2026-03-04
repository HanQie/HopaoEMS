import os
import json
import sqlite3
import sys

# Setup Paths
ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC_PATH = os.path.join(ROOT_PATH, 'src')
CONTRACT_FILE = os.path.join(SRC_PATH, 'hopaoems', 'contracts', 'db_schema_contract.json')

sys.path.append(SRC_PATH)

def get_db_schema(db_path=":memory:"):
    from hopaoems.app_factory import create_app
    from hopaoems.services import db as db_service
    from hopaoems.services import schema_migrations
    
    app = create_app({'TESTING': True, 'DATABASE': db_path, 'WTF_CSRF_ENABLED': False})
    
    with app.app_context():
        # Ensure schema is initialized
        schema_migrations.init_schema()
        
        conn = db_service.get_db()
        cursor = conn.cursor()
        
        # 1. Get Tables (Sorted for determinism)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        schema = {
            "version": 1,
            "tables": {}
        }
        
        for table in tables:
            # 2. Get Columns
            cursor.execute(f"PRAGMA table_info({table})")
            columns = []
            for col in cursor.fetchall():
                columns.append({
                    "name": col[1],
                    "type": col[2],
                    "notnull": col[3],
                    "default": col[4],
                    "pk": col[5]
                })
            # Sort columns by name for determinism? 
            # Actually table_info order is meaningful (SQL order), but name order is safer for contract comparison.
            # Let's keep SQL order but sort it for JSON.
            
            # 3. Get Indexes
            cursor.execute(f"PRAGMA index_list({table})")
            indexes = []
            for idx in cursor.fetchall():
                idx_name = idx[1]
                unique = idx[2]
                origin = idx[3] # 'c' for CREATE INDEX, 'u' for UNIQUE constraint, 'pk' for PRIMARY KEY
                
                cursor.execute(f"PRAGMA index_info({idx_name})")
                idx_cols = []
                for icol in cursor.fetchall():
                    idx_cols.append(icol[2])
                
                indexes.append({
                    "name": idx_name,
                    "unique": unique,
                    "columns": idx_cols
                })
            
            # 4. Get Foreign Keys
            cursor.execute(f"PRAGMA foreign_key_list({table})")
            fks = []
            for fk in cursor.fetchall():
                fks.append({
                    "table": fk[2],
                    "from": fk[3],
                    "to": fk[4],
                    "on_update": fk[5],
                    "on_delete": fk[6]
                })
            
            schema["tables"][table] = {
                "columns": columns,
                "indexes": sorted(indexes, key=lambda x: x['name']),
                "foreign_keys": sorted(fks, key=lambda x: (x['table'], x['from']))
            }
            
    return schema

def main():
    print("Exporting DB Schema Contract...")
    schema = get_db_schema()
    
    # Save to file
    with open(CONTRACT_FILE, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, sort_keys=True)
    
    print(f"Contract saved to: {CONTRACT_FILE}")
    print(f"Total Tables: {len(schema['tables'])}")

if __name__ == "__main__":
    main()
