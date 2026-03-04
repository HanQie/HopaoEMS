
from flask import Blueprint, render_template, g
from ..services import auth_service, production_repo
from ..services.i18n import t

bp = Blueprint('ui', __name__)

@bp.route('/data/uploads/samples/<path:filename>')
def sample_image(filename):
    from flask import send_from_directory, current_app, abort
    # Strict Path Traversal Check
    # Allow "." (extensions) but disallow ".." (traversal)
    if ".." in filename or filename.startswith("/") or filename.startswith("\\") or ":" in filename:
        abort(404)
    
    # Also forbid backslashes to prevent sub-directory escape on Windows
    if "\\" in filename:
        abort(404)
        
    directory = current_app.config['SAMPLES_UPLOAD_DIR']
    return send_from_directory(directory, filename)

@bp.route('/data/swatches/<hex_code>.png')
def color_swatch(hex_code):
    """Return a 16x16 pure color PNG for the given hex code."""
    from PIL import Image
    import io
    from flask import send_file, abort
    
    # Handle optional hash prefix (though URL usually doesn't like it)
    clean_hex = hex_code.lstrip('#')
    if len(clean_hex) != 6:
        abort(400)
    
    try:
        r = int(clean_hex[0:2], 16)
        g = int(clean_hex[2:4], 16)
        b = int(clean_hex[4:6], 16)
    except ValueError:
        abort(400)
        
    img = Image.new('RGB', (16, 16), color=(r, g, b))
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

@bp.route('/')
def index():
    # Home Dashboard (Viewer or Operator)
    stats = production_repo.get_dashboard_stats()
    return render_template('index.html', stats=stats)



@bp.route('/i18n/set/<lang>')
def set_lang(lang):
    from flask import redirect, request, session, url_for
    from ..services.i18n import normalize_locale
    
    target_lang = normalize_locale(lang)
    session['lang'] = target_lang
    
    next_url = request.args.get('next')
    # Safe redirect check: Must start with / and not //
    if not next_url or not next_url.startswith('/') or next_url.startswith('//'):
        next_url = url_for('ui.index')
        
    return redirect(next_url)

@bp.route('/dashboard')
def legacy_dashboard():
    from flask import redirect, url_for
    return redirect(url_for('ui.index'), code=302)

@bp.route('/old-production')
def legacy_old_production():
    from flask import redirect, url_for
    return redirect(url_for('ui_production.production_dashboard'), code=302)
@bp.route('/__debug/build')
@auth_service.operator_required
def debug_build_info():
    """Return build and path info for verification."""
    from flask import current_app, jsonify
    import os
    
    # Get asset version re-calc for real-time check
    ui_js_path = os.path.join(current_app.static_folder, 'js', 'ui.js')
    try:
        mtime = int(os.path.getmtime(ui_js_path))
    except:
        mtime = 0
        
    return jsonify({
        'template_folder': current_app.template_folder,
        'static_folder': current_app.static_folder,
        'ui_js_build_id': mtime,
        'root_path': current_app.root_path
    })

@bp.route('/__debug/whoami')
@auth_service.operator_required
def debug_whoami():
    """Debug endpoint for session and user state."""
    from flask import session, jsonify
    from ..services.db import query_db
    
    db_user = None
    if g.user:
        db_user = query_db('SELECT id, username, role FROM users WHERE id = ?', (g.user['id'],), one=True)
        if db_user:
            db_user = dict(db_user)
            
    return jsonify({
        'session_user_id': session.get('user_id'),
        'auth_source': getattr(g, 'auth_source', 'unknown'),
        'g_user': dict(g.user) if g.user else None,
        'db_user': db_user,
        'role_raw': db_user['role'] if db_user else None
    })

@bp.route('/__debug/i18n')
@auth_service.operator_required
def debug_i18n():
    """Debug endpoint for I18N configuration and state."""
    from flask import current_app, session, jsonify
    import os
    from ..services.i18n import get_locale, t
    
    root_path = current_app.root_path
    seed_dir = os.path.join(root_path, 'i18n')
    
    translations = current_app.extensions.get('i18n_translations', {})
    
    key_counts = {
        'en': len(translations.get('en', {})),
        'zh-TW': len(translations.get('zh-TW', {})),
        'vi': len(translations.get('vi', {}))
    }
    
    # Random key check
    samples = {
        'main.title': t('main.title'), # dashboard title
        'auth.login.title': t('auth.login.title'),
        'common.save': t('common.save')
    }
    
    return jsonify({
        'root_path': root_path,
        'seed_dir': seed_dir,
        'key_counts': key_counts,
        'resolved_locale': get_locale(),
        'session_lang': session.get('lang'),
        'sample_values': samples,
        'extensions_cache_present': 'i18n_translations' in current_app.extensions
    })
