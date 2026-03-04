
import functools
from flask import g, session, request, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from .db import query_db

def login_user(username, password):
    """Authenticate user and set session."""
    user = query_db('SELECT * FROM users WHERE username = ?', (username,), one=True)
    
    if user is None:
        return {'success': False, 'message': 'auth.error.invalid'}
        
    if not check_password_hash(user['password_hash'], password):
        return {'success': False, 'message': 'auth.error.invalid'}
        
    session.clear()
    session['user_id'] = user['id']
    return {'success': True, 'user': user}

def logout_user():
    """Clear session."""
    session.clear()

def load_logged_in_user():
    """Load user from session into g.user."""
    user_id = session.get('user_id')
    
    if user_id is None:
        g.user = None
        g.auth_source = 'none'
    else:
        g.user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
        g.auth_source = 'session' if g.user else 'not_found'

def is_operator():
    """Check if current user is an operator."""
    return g.user and g.user['role'] == 'operator'

def is_viewer():
    """Check if current user is a viewer."""
    return g.user and g.user['role'] == 'viewer'

def login_required(view):
    """Decorator to require login."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            if request.method == 'GET':
                return redirect(url_for('auth.login', next=request.path))
            return "Login Required", 401
        return view(**kwargs)
    return wrapped_view

def operator_required(view):
    """Decorator to require operator role."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            if request.method == 'GET':
                return redirect(url_for('auth.login', next=request.path))
            return "Login Required", 401
        if not is_operator():
            return "Forbidden: Operators Only", 403
        return view(**kwargs)
    wrapped_view._requires_operator = True
    return wrapped_view
