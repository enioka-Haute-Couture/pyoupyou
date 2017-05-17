from pyoupyou.settings.common import *

DEBUG = True

# Value used for local dev environment for security reason never use it in prod...
SECRET_KEY = 'e1*u0nqk5k^j_mirkhetnq%!1+#*op*57cju44n^1tg=67*ij@'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# flag to add Django Debug Toolbar to urls.py
HAS_DDT = True

INSTALLED_APPS += [
    'debug_toolbar',
    'debug_toolbar_user_panel',
]

MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
]

DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar_user_panel.panels.UserPanel',
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.logging.LoggingPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
]

# needed by django debug toolbar
INTERNAL_IPS = ['127.0.0.1', ]
