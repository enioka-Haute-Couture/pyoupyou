#!/bin/sh

python manage.py makemessages -i "venv/*" -i "migrations/*" -i "tests.py" -i "media/*" -i "static/*" -v2 -a -e "html,py"
python manage.py compilemessages
