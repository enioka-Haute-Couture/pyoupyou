**pyoupyou** is a recruitment management software that make life easier for all people involved in the recruitment process

# LICENSE

pyoupyou is available under the GNU Affero Public License v3 or newer (AGPL 3+).
http://www.gnu.org/licenses/agpl-3.0.html

# Install

## Dependencies

- Python ~= 3.11
- uv

## Dev environment

```
uv sync --dev
```

## Prod environment

```
uv sync
```

# Contribute

To contribute do Pull Request against this repository (https://github.com/enioka-Haute-Couture/pyoupyou)

In order to create a branch from an issue use github name suggestion <issue-id>-issue-name

## Style Guide

We use black to enforce coding style, you just need to run `black .` before commiting.

### Formatting string

To format string using format will be prefered over the % syntax. In order to facilitate translation we will use named placeholder

```
"This is a {state} example".format(state="good")
```

# Setup dev

```
# Switch to virtualenv (created with uv sync)
source .venv/bin/activate

# set environment to dev, will load settings in pyoupyou/settings/dev.py
export PYOUPYOU_ENV=dev

# Migrate Database, create schema ....
python manage.py migrate

# Cleanup all data in database
python manage.py flush

# Generate dev dataset
python manage.py create_dev_dataset

# Create a superuser, for instance call it "root"
python manage.py createsuperuser

# Force every dev dataset generate users to have same password than root
sqlite3 "db.sqlite3" "update ref_pyoupyouuser set password = (select password from ref_pyoupyouuser where trigramme='root');"

# Allow connection from everywhere (by default Django restricts to 127.0.0.1)
echo "ALLOWED_HOSTS = ['*']" >> pyoupyou/settings/dev.py

# launch the dev server
python manage.py runserver
# pyoupyou is now launched at http://127.0.0.1:8000/

# if you want pyoupyou to be reachable from elsewhere (e.g. if you run it in a container)
python manage.py runserver 0.0.0.0:8000

```
# Setup dev env within a docker container
If you wan't to install and run a dev/demo pyoupyou instance within a docker
container (for instance to avoid messing your computer with python dependencies)
these commands before before uv sync and setup dev procedure are the way to go:
```
docker run -ti -p 8000:8000 debian:12.10-slim
apt update
apt upgrade
apt install git pip vim sqlite3
pip install uv --break-system-packages
git clone https://github.com/enioka-Haute-Couture/pyoupyou.git
cd pyoupyou
```

# Setup prod

## Create local settings file

Based on local.py.example create a local.py file containing keys referenced by local.py.example and database configuration.

https://docs.djangoproject.com/en/2.2/ref/settings/#databases

## Install dependencies, collect static and migrate database

```
# install dependencies using uv sync or pip install -r requirements.txt

# activate env
source .venv/bin/activate

# collect static files
PYOUPYOU_ENV="prod" ./manage.py collectstatic

# migrate database
PYOUPYOU_ENV="prod" ./manage.py migrate

```

## Run

In order to run it you can use a wsgi capable webserver (apache mod_wsgi, gunicorn, uWSGI...), ensure to set PYOUPYOU_ENV variable to _prod_ or _dev_.

As an alternative you can also set name in pyoupyou/.pyoupyou_env file.
