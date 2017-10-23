try:
    from pyoupyou.settings.local import *
except ImportError:
    print("You need to create a settings/local.py file. You can use local.example.py to help you")
    exit()

try:
    DATABASES
except NameError:
    print("You need to declare a database settings in your settings/local.py file")

