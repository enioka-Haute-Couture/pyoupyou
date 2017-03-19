# You MUST import dev or prod settings in you local file
from django.core.management.utils import get_random_secret_key

from pyoupyou.settings.dev import *
# from pyoupyou.settings.prod import *

# If you are using prod settings you need to fill the following keys
# ALLOWED_HOSTS = []
# SECRECT_KEY = '' # You can use the following command: generate_secret_key from django extensions
