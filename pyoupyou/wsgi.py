"""
WSGI config for pyoupyou project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application


def get_pyoupyou_env_from_file():
    try:
        with open(os.path.join(os.path.dirname(__file__), ".pyoupyou_env")) as f:
            return f.read().strip()
    except Exception:
        return ""


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pyoupyou.settings")
os.environ.setdefault("PYOUPYOU_ENV", get_pyoupyou_env_from_file())

application = get_wsgi_application()
