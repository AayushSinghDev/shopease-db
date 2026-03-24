# ShopEase — Django E-Commerce Platform

## 🚀 Quick Start (Windows)

### Step 1: Install Dependencies
```
pip install -r requirements.txt
```

### Step 2: Setup MySQL Database
Create a MySQL database named `shopease_db`:
```sql
CREATE DATABASE shopease_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Step 3: Configure Environment (Optional)
Set these environment variables if needed:
```
set DB_NAME=shopease_db
set DB_USER=root
set DB_PASSWORD=your_mysql_password
set DB_HOST=localhost
```
OR edit `ShopEase/settings.py` defaults directly (lines with `os.environ.get`).

### Step 4: Run Migrations
```
python manage.py migrate
```

### Step 5: Create Admin (Optional)
Use the DB to create a SuperAdmin record, or use the existing SQL fix files.

### Step 6: Run Server
```
python manage.py runserver
```

Visit: http://127.0.0.1:8000

## 📝 Notes
- No `python-decouple` needed — uses standard `os.environ`
- Default DB: MySQL on localhost with root/root
- Email & Razorpay: Set via environment variables (optional for dev)
- Media files: Uploaded to `media/` folder automatically

## 🔒 Security Fixes Applied
- No hardcoded secrets — all via env vars
- Brute-force login protection (5 attempts = 15min lockout)
- Atomic stock deduction (race condition safe)
- Seller approval checked from DB (not just session)
- Demo payment bypass REMOVED
- Password strength: min 8 chars + letter + digit
- Image upload validation (type + size)
