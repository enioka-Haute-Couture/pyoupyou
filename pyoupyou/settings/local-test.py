from django.core.management.utils import get_random_secret_key

from pyoupyou.settings.dev import *

SECRET_KEY = '122' # You can use the following command: generate_secret_key from django extensions
LOGIN_URL='/admin/login/'


MAIL_HR = 'hr@pyoupyou.com'
MAIL_FROM = 'pyoupyou@pyoupyou.com'
SITE_HOST = 'http://localhost:8000'
