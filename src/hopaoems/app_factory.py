import os
from flask import Flask, request, has_request_context
from jinja2 import BaseLoader, TemplateNotFound, FileSystemLoader
from .services import db, i18n

class MobileTemplateLoader(BaseLoader):
    """
    自定義的 Template Loader，用於實作設備嗅探與手機版視圖攔截。
    當判定為手機設備時，優先去 mobile_templates/ 尋找對應的 HTML。
    如果找不到或是電腦設備，自動 fallback 回原本的 templates/。
    這個層級的攔截不會影響任何業務邏輯、路由或後端驗證。
    """
    def __init__(self, mobile_folder, desktop_folder):
        self.mobile_loader = FileSystemLoader(mobile_folder)
        self.desktop_loader = FileSystemLoader(desktop_folder)

    def get_source(self, environment, template):
        is_mobile = False
        if has_request_context():
            user_agent = request.user_agent.string.lower()
            # 常見的手機裝置關鍵字
            if any(kw in user_agent for kw in ['mobi', 'android', 'iphone', 'ipad', 'ipod']):
                is_mobile = True
        
        if is_mobile:
            try:
                # 優先嘗試載入手機版模板
                return self.mobile_loader.get_source(environment, template)
            except TemplateNotFound:
                # 該模板在手機版目錄還沒建立，fallback 到常規版
                pass
                
        return self.desktop_loader.get_source(environment, template)
        
    def list_templates(self):
        templates = set()
        templates.update(self.mobile_loader.list_templates())
        templates.update(self.desktop_loader.list_templates())
        return list(templates)

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
    
    # 動態建立 mobile_templates 資料夾（如果不存在的話）
    mobile_templates_dir = os.path.join(root_path, 'mobile_templates')
    os.makedirs(mobile_templates_dir, exist_ok=True)
    
    # 覆寫並套用自定義的 Jinja2 Template Loader
    app.jinja_env.loader = MobileTemplateLoader(
        mobile_folder=mobile_templates_dir,
        desktop_folder=app.template_folder
    )
    
    # 關閉 Jinja2 的內部 AST 緩存以避免電腦版與手機版拿到錯誤的快取（Template Name 相同導致的碰撞）
    app.jinja_env.cache = None
    
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
        MAX_CONTENT_LENGTH=None, # 無上限 (No limit)
        OLLAMA_MODEL='qwen2.5:7b',
        OLLAMA_VL_MODEL='qwen3-vl:4b',
        OLLAMA_OCR_MODEL='qwen3-vl:4b',
        OLLAMA_AUTO_PULL_MODELS=True,
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

    # Initialize AI Engine (lazy-fail: logs warning if model path not set)
    from .ai_engine import init_ai_engine
    init_ai_engine(app)

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
    from .blueprints import api_ai
    app.register_blueprint(api_ai.bp)

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
