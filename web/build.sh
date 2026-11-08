#!/usr/bin/env bash
# Сборка проекта на Render. Выполняется при каждом деплое.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py seed_demo --base
python manage.py remove_demo
python manage.py add_gulvar
python manage.py add_partners
python manage.py ensure_superuser
