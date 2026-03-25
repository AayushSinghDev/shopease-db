import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ShopEase.settings')
django.setup()

from django.db import connection

sql_file = os.path.join(os.path.dirname(__file__), 'shopease_postgres_import.sql')
with open(sql_file, 'r') as f:
    sql = f.read()

with connection.cursor() as cursor:
    cursor.execute(sql)

print("✅ Database import successful!")
