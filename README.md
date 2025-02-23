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

# launch the dev server
python manage.py runserver
# pyoupyou is now launched at http://127.0.0.1:8000/
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
