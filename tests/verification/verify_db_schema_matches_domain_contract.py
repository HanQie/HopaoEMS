
import sqlite3
import re
import os
import sys

def parse_contract_tables(md_path):
    """Parse markdown tables from domain_contract.md."""
    # Look for | Table | Column | ...
    # Store as {table: {col: type}} (Simplification)
    # The contract has Table, Column, Type, Constraints. 
    # We focus on Table/Column existence primarily.
    
    tables = {}
    current_table = None
    
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        if line.strip().startswith('|'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 4: continue
            
            # parts[1] is Table, parts[2] is Column
            t_name = parts[1].strip('`')
            c_name = parts[2].strip('`')
            
            if t_name == 'Table' or '---' in t_name: continue
            
            if t_name: 
                current_table = t_name
                if current_table not in tables:
                    tables[current_table] = set()
            
            if c_name and current_table:
                tables[current_table].add(c_name)
                
    return tables

def get_db_schema(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # List tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'")
    db_tables = cur.fetchall()
    
    schema = {}
    for (t_name,) in db_tables:
        schema[t_name] = set()
        cur.execute(f"PRAGMA table_info({t_name})")
        cols = cur.fetchall()
        for col in cols:
            # col[1] is name
            schema[t_name].add(col[1])
            
    return schema

def verify_schema():
    contract_path = os.path.join('src', 'hopaoems', 'contracts', 'domain_contract.md')
    # Locate DB: src/instance/hopaoems.sqlite
    db_path = os.path.join('src', 'instance', 'hopaoems.sqlite')
    
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}. Run app first/init db.")
        # Try to initialize?
        # Let's assume verifying after run. Or we can init.
        # Strict gate: Fail if no DB.
        print("FAIL: DB does not exist")
        sys.exit(1)
        
    contract = parse_contract_tables(contract_path)
    schema = get_db_schema(db_path)
    
    violations = []
    
    # 1. Check Tables
    missing_tables = set(contract.keys()) - set(schema.keys())
    if missing_tables:
        violations.append(f"MISSING TABLES: {missing_tables}")
        
    # 2. Check Columns
    for t_name, c_cols in contract.items():
        if t_name in schema:
            d_cols = schema[t_name]
            missing_cols = c_cols - d_cols
            if missing_cols:
                violations.append(f"TABLE {t_name} MISSING COLUMNS: {missing_cols}")
                
    if violations:
        print("\n".join(violations))
        sys.exit(1)
        
    print("SCHEMA CONTRACT PASSED")

if __name__ == '__main__':
    verify_schema()
