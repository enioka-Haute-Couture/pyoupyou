#!/bin/sh

python manage.py makemessages -i "venv/*" -i "migrations/*" -i "tests.py" -i "media/*" -v2 -a -e "html,py"
python manage.py compilemessages
