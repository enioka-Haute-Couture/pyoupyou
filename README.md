[![CircleCI](https://circleci.com/gh/pyoupyou/pyoupyou/tree/master.svg?style=svg)](https://circleci.com/gh/pyoupyou/pyoupyou/tree/master)

**pyoupyou** is a recruitment management software that make life easier for all people involved in the recruitment process
 
# LICENSE

pyoupyou is available under the GNU Affero Public License v3 or newer (AGPL 3+).
http://www.gnu.org/licenses/agpl-3.0.html

# Install

## Dependencies

- Python >= 3.5
- pipenv

## Dev environment

```
pipenv install --dev
```

## Prod environment

```
- pipenv install
```

# Contribute

To contribute do Pull Request against this repository (https://github.com/pyoupyou/pyoupyou)

## Style Guide

We use black to enforce coding style, you just need to run `black .` before commiting.

### Formatting string

To format string using format will be prefered over the % syntax. In order to facilitate translation we will use named placeholder

```
"This is a {state} example".format(state="good")
```

# Setup prod

## Create local settings file

Based on local.py.example create a local.py file containing keys referenced by local.py.example and database configuration.

https://docs.djangoproject.com/en/2.2/ref/settings/#databases

## Install dependencies, collect static and migrate database
```
# install dependencies
export PIPENV_VENV_IN_PROJECT=true # To create virtualenv on the project folder under .venv
pipenv install

# collect static files
PYOUPYOU_ENV="prod" pipenv run ./manage.py collectstatic

# migrate database
PYOUPYOU_ENV="prod" pipenv run ./manage.py migrate

```

## Run

In order to run it you can use a wsgi capable webserver (apache mod_wsgi, gunicorn, uWSGI...), ensure to set PYOUPYOU_ENV variable to *prod*
