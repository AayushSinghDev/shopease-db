import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ShopEase.settings')
django.setup()

import psycopg2
import dj_database_url

print("Starting import...")

DATABASE_URL = os.environ.get('DATABASE_URL')
config = dj_database_url.parse(DATABASE_URL)

conn = psycopg2.connect(
    host=config['HOST'],
    port=config['PORT'],
    dbname=config['NAME'],
    user=config['USER'],
    password=config['PASSWORD']
)
conn.autocommit = True

sql_file = os.path.join(os.path.dirname(__file__), 'shopease_postgres_import.sql')
with open(sql_file, 'r') as f:
    sql = f.read()

cursor = conn.cursor()
cursor.execute(sql)
cursor.close()
conn.close()

print("✅ Import complete!")
