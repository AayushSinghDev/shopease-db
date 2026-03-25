import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ShopEase.settings')
django.setup()

from django.db import connection

sql_file = os.path.join(os.path.dirname(__file__), 'shopease_postgres_import.sql')

print("Starting import...")
with open(sql_file, 'r') as f:
    sql = f.read()

# psycopg2 ke saath ye kaam karta hai
from django.db import connection
conn = connection.connection
conn.autocommit = True
cursor = conn.cursor()
cursor.execute(sql)
conn.autocommit = False
print("✅ Import complete!")
