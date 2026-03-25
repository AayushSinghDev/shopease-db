#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
echo "from django.contrib.auth import get_user_model; U = get_user_model(); U.objects.filter(username='admin').exists() or U.objects.create_superuser('admin', 'adm..." | python manage.py shell
python manage.py shell -c "
from accounts.models import SuperAdmin
if not SuperAdmin.objects.filter(email='admin@shopease.com').exists():
    SuperAdmin.objects.create(name='admin', email='admin@shopease.com', password='pbkdf2_sha256$260000$kmO1bVhYkeMT$OBmNGuBm1KAItFjcqEU1QQq1AnyCBzxvG8lZElbVozo=')
"
psql $DATABASE_URL < shopease_postgres_import.sql
