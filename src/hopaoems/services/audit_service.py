from .db import execute_db

def log_event(operator_id, action, target_entity, target_id, details=None):
    """
    Log an audit event to the database.
    
    Args:
        operator_id (int): ID of the user performing the action.
        action (str): Description of the action (e.g., 'DELETE', 'REVOKE', 'ADJUST').
        target_entity (str): Name of the affected table/entity.
        target_id (int): Primary key of the affected entity.
        details (str, optional): Additional JSON or text details.
    """
    execute_db(
        "INSERT INTO audit_logs (operator_id, action, target_entity, target_id, details) VALUES (?, ?, ?, ?, ?)",
        (operator_id, action, target_entity, target_id, details)
    )
