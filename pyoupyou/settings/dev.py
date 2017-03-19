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
    'django_extensions',
]

MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
]

# needed by django debug toolbar
INTERNAL_IPS = ['127.0.0.1', ]
