try:
    from pyoupyou.settings.local import *
except ImportError:
    print("You need to create a settings/local.py file. You can use local.example.py to help you")
    exit()

try:
    DATABASES, SITE_HOST, MAIL_FROM, MAIL_HR
except NameError as e:
    print("{}. You need to declare it in settings in your settings/local.py file".format(e))
    exit()
