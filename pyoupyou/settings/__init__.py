import os

from split_settings.tools import optional, include

env = os.environ.get("PYOUPYOU_ENV", None)

if env not in ("dev", "prod"):
    print("You need to set PYOUPYOU_ENV environment variable to 'dev' or 'prod'")
    exit()

include("common.py", "{env}.py".format(env), optional("local.py"))


try:
    DATABASES, SITE_HOST, MAIL_FROM, MAIL_HR
except NameError as e:
    print("{}. You need to declare it in settings in your settings/local.py file".format(e))
    exit()
