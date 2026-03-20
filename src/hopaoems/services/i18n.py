
import json
import os
# Force reload to refresh i18n cache
from flask import request, current_app, session

def normalize_locale(lang):
    """Normalize locale strings to standard format (en, zh-TW, vi)."""
    if not lang:
        return 'en'
    lang = lang.lower().replace('_', '-')
    if 'zh-tw' in lang or 'zh-hant' in lang or 'tw' in lang:
        return 'zh-TW'
    if 'zh' in lang: # Generic zh fallback to tw for this app
        return 'zh-TW'
    if 'vi' in lang:
        return 'vi'
    return 'en'

def get_locale():
    """Determine best locale: URL param > Session > Browser > Default."""
    # 1. URL parameter (e.g. ?lang=zh-TW)
    lang = request.args.get('lang')
    if lang:
        normalized = normalize_locale(lang)
        if normalized in ['en', 'zh-TW', 'vi']:
            session['lang'] = normalized
            return normalized
            
    # 2. Session
    if 'lang' in session:
        return normalize_locale(session['lang'])
        
    # 3. Browser Accept-Language
    best = request.accept_languages.best_match(['en', 'zh-TW', 'vi'])
    if best:
        return normalize_locale(best)
    
    # 4. Default
    return 'en'

def t(key, **kwargs):
    """Translate key with fallback to English then ID, using App-Level Cache."""
    locale = get_locale()
    
    # Access translations from App Extensions
    # Fallback only during tests where app context might be incomplete
    translations = current_app.extensions.get('i18n_translations', {})
    
    # 1. Try target locale
    val = translations.get(locale, {}).get(key)
    if val == "hardcoded": val = None
    
    # 2. Fallback to English
    if val is None and locale != 'en':
        val = translations.get('en', {}).get(key)
        if val == "hardcoded": val = None
        
    # 3. Fallback to Key
    if val is None:
        return key
        
    # Interpolation
    if kwargs:
        try:
            # Support %{var} syntax if used in seeds, or simple .format()
            # Assuming simple python .format for now or explicit replace if needed.
            # Safety: use safe replace for known keys to avoid KeyErrors
            for k, v in kwargs.items():
                # Try both {k} and %{k}
                val = val.replace(f'%{{{k}}}', str(v))
                val = val.replace(f'{{{k}}}', str(v))
        except Exception:
            pass
            
    return val

def init_app(app):
    """Initialize i18n service: Load seeds into memory once at startup."""
    translations = {}
    langs = ['en', 'zh-TW', 'vi']
    
    # Correct path: src/hopaoems/i18n
    # app.root_path is usually .../src/hopaoems
    base_dir = os.path.join(app.root_path, 'i18n')
    
    # print(f"i18n: Loading translations from {base_dir}")

    for lang in langs:
        seed_path = os.path.join(base_dir, f'seed.{lang}.json')
        if not os.path.exists(seed_path):
            raise RuntimeError(f"CRITICAL: Missing i18n seed file: {seed_path}")
            
        try:
            with open(seed_path, 'r', encoding='utf-8') as f:
                translations[lang] = json.load(f)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"CRITICAL: Failed to parse i18n seed file {seed_path}: {e}")
            
    # Store in App Extensions (Global Cache)
    app.extensions['i18n_translations'] = translations
    
    # Register Globals
    app.jinja_env.globals['t'] = t
    app.jinja_env.globals['get_locale'] = get_locale
    
    # print(f"i18n: Successfully loaded {len(langs)} languages.")
