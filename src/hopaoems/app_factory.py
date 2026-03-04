
import os
from flask import Flask
from .services import db, i18n

def create_app(test_config=None):
    # root_path: .../src/hopaoems
    root_path = os.path.dirname(os.path.abspath(__file__))
    # project_src: .../src
    project_src = os.path.dirname(root_path)
    # samples_upload_dir: .../src/data/uploads/samples
    samples_upload_dir = os.path.join(project_src, 'data', 'uploads', 'samples')
    
    app = Flask(__name__, 
                instance_relative_config=True,
                static_folder=os.path.join(project_src, 'static'),
                static_url_path='/static',
                template_folder=os.path.join(root_path, 'templates'))
    
    app.config['SAMPLES_UPLOAD_DIR'] = samples_upload_dir

    # Source Lock paths validation log
    # print(f"--- [SOURCE LOCK ACTIVATED] ---")
    # print(f"Project Src:   {project_src}")
    # print(f"Upload Dir:    {samples_upload_dir}")
    # print(f"Template Path: {app.template_folder}")
    # print(f"Static Folder: {app.static_folder}")
    # print(f"i18n Path:     {os.path.join(app.root_path, 'i18n')}")
    # print(f"-------------------------------")
    
    # Default Configuration
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'hopaoems.sqlite'),
        MAX_CONTENT_LENGTH=30 * 1024 * 1024, # 30MB limit
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize Services
    db.init_app(app)
    from .services import schema_migrations, auth_service
    with app.app_context():
        schema_migrations.init_schema()
    i18n.init_app(app)

    # D) Global User Loader
    app.before_request(auth_service.load_logged_in_user)

    # Register Globals for Macros (Fix scope issues)
    app.jinja_env.globals.update(
        is_operator=auth_service.is_operator,
        is_viewer=auth_service.is_viewer
    )

    # Register Blueprints
    from .blueprints import auth, ui_fabric, ui_sample, ui_ink, ui_order, ui_production, ui_wash, ui_settings, ui_main
    app.register_blueprint(ui_main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(ui_fabric.bp)
    app.register_blueprint(ui_sample.bp)
    app.register_blueprint(ui_ink.bp)
    app.register_blueprint(ui_order.bp)
    app.register_blueprint(ui_production.bp)
    app.register_blueprint(ui_wash.bp)
    app.register_blueprint(ui_settings.bp)

    # E) Context Processors
    @app.context_processor
    def inject_helpers():
        from .services import auth_service
        # Calculate version based on static/js/ui.js modification time
        try:
            ui_js_path = os.path.join(app.static_folder, 'js', 'ui.js')
            mtime = os.path.getmtime(ui_js_path)
            version = int(mtime)
        except Exception:
            version = 1
        return dict(
            asset_version=version,
            is_operator=auth_service.is_operator,
            is_viewer=auth_service.is_viewer
        )

    return app
