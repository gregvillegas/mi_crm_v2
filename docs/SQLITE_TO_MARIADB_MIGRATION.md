# SQLite3 to MariaDB Migration Guide

**Project:** MiCRM  
**Server:** Ubuntu (10.10.10.2)  
**Date:** August 2026

---

## Overview

This guide migrates the CRM database from SQLite3 to MariaDB. The Django settings already support both — you only need to change `DB_ENGINE=mariadb` in `.env` after setting up MariaDB and importing the data.

**Why migrate:**
- SQLite locks the entire database file on writes (causes "database is locked" errors with multiple users)
- MariaDB handles concurrent users properly (row-level locking)
- Better performance for queries on large datasets

---

## Prerequisites

- SSH access to the production server (10.10.10.2)
- Root or sudo access to install MariaDB
- The CRM application stopped during migration (brief downtime ~10-15 minutes)

---

## Step-by-Step Migration

### Step 1: Install MariaDB on Ubuntu

```bash
sudo apt update
sudo apt install mariadb-server mariadb-client libmariadb-dev -y
sudo systemctl start mariadb
sudo systemctl enable mariadb
```

Secure the installation:
```bash
sudo mysql_secure_installation
```
- Set root password: (choose a strong password)
- Remove anonymous users: Yes
- Disallow root login remotely: Yes
- Remove test database: Yes
- Reload privilege tables: Yes

### Step 2: Create the Database and User

```bash
sudo mysql -u root -p
```

Run these SQL commands inside the MariaDB shell:

```sql
CREATE DATABASE mi_crm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'mi_crm_user'@'localhost' IDENTIFIED BY 'YOUR_STRONG_PASSWORD_HERE';

GRANT ALL PRIVILEGES ON mi_crm.* TO 'mi_crm_user'@'localhost';

FLUSH PRIVILEGES;

EXIT;
```

**Important:** Replace `YOUR_STRONG_PASSWORD_HERE` with a strong password. Note it down — you'll need it for the `.env` file.

### Step 3: Install Python MySQL Client (if not already installed)

```bash
cd /var/www/mi_crm
source venv/bin/activate
pip install mysqlclient
```

If `mysqlclient` fails to compile, install the build dependencies first:
```bash
sudo apt install python3-dev default-libmysqlclient-dev build-essential pkg-config -y
pip install mysqlclient
```

### Step 4: Export Data from SQLite3

While the CRM is still running on SQLite, export all data:

```bash
cd /var/www/mi_crm
source venv/bin/activate

# Export all data to a JSON fixture (preserves all relationships)
python manage.py dumpdata --natural-foreign --natural-primary --indent=2 -o full_backup.json
```

**Verify the export:**
```bash
ls -lh full_backup.json
# Should be a few MB depending on data volume
```

**Alternative: Export specific apps (if full export is too large):**
```bash
python manage.py dumpdata users teams customers sales_proposals sales_funnel sales_monitoring customer_service mass_mailing lead_generation gamification --natural-foreign --natural-primary --indent=2 -o full_backup.json
```

### Step 5: Stop the CRM Application

```bash
# If using gunicorn/systemd:
sudo systemctl stop mi_crm

# Or if using supervisor:
sudo supervisorctl stop mi_crm
```

### Step 6: Update the .env File

Edit `/var/www/mi_crm/.env`:

```bash
nano /var/www/mi_crm/.env
```

Change these values:
```ini
# BEFORE (SQLite)
DB_ENGINE=sqlite3

# AFTER (MariaDB)
DB_ENGINE=mariadb
DB_NAME=mi_crm
DB_USER=mi_crm_user
DB_PASSWORD=YOUR_STRONG_PASSWORD_HERE
DB_HOST=127.0.0.1
DB_PORT=3306
DB_CONN_MAX_AGE=60
```

### Step 7: Run Migrations on MariaDB (Create Tables)

```bash
cd /var/www/mi_crm
source venv/bin/activate

# This creates all tables in MariaDB (empty)
python manage.py migrate
```

You should see all migrations applied successfully. If any errors occur, check that `mysqlclient` is installed and the database credentials are correct.

### Step 8: Load Data into MariaDB

```bash
python manage.py loaddata full_backup.json
```

**This may take 1-5 minutes depending on data volume.**

If you get errors about content types or permissions conflicts:
```bash
# Clear default content types first, then reload
python manage.py shell -c "
from django.contrib.contenttypes.models import ContentType
ContentType.objects.all().delete()
"
python manage.py loaddata full_backup.json
```

### Step 9: Verify the Data

```bash
python manage.py shell -c "
from customers.models import Customer
from users.models import User
from sales_proposals.models import Proposal
from sales_funnel.models import SalesFunnel

print(f'Users: {User.objects.count()}')
print(f'Customers: {Customer.objects.count()}')
print(f'Proposals: {Proposal.objects.count()}')
print(f'Funnel entries: {SalesFunnel.objects.count()}')
print('All counts look correct!')
"
```

Compare these numbers against what you had in SQLite. They should match exactly.

### Step 10: Start the CRM Application

```bash
# If using gunicorn/systemd:
sudo systemctl start mi_crm

# Or if using supervisor:
sudo supervisorctl start mi_crm
```

### Step 11: Test the Application

1. Login as admin — verify the dashboard loads
2. Login as a salesperson — verify proposals and funnel entries are visible
3. Try creating a new proposal
4. Try approving a customer request (the operation that was causing "database is locked")
5. Have two users login simultaneously and perform actions — no more locking

### Step 12: Backup the Old SQLite File

```bash
# Keep the old SQLite file as a backup (don't delete it yet)
mv /var/www/mi_crm/db.sqlite3 /var/www/mi_crm/db.sqlite3.backup.$(date +%Y%m%d)
```

---

## Rollback (If Something Goes Wrong)

If the migration fails and you need to revert:

```bash
# 1. Stop the application
sudo systemctl stop mi_crm

# 2. Revert .env to SQLite
nano /var/www/mi_crm/.env
# Change DB_ENGINE=mariadb back to DB_ENGINE=sqlite3

# 3. Restore the SQLite file
mv /var/www/mi_crm/db.sqlite3.backup.YYYYMMDD /var/www/mi_crm/db.sqlite3

# 4. Restart
sudo systemctl start mi_crm
```

---

## Troubleshooting

### "Access denied for user 'mi_crm_user'@'localhost'"

The password in `.env` doesn't match what was set in MariaDB. Fix:
```bash
sudo mysql -u root -p
ALTER USER 'mi_crm_user'@'localhost' IDENTIFIED BY 'correct_password';
FLUSH PRIVILEGES;
EXIT;
```

### "mysqlclient" package not found

```bash
sudo apt install python3-dev default-libmysqlclient-dev build-essential pkg-config -y
pip install mysqlclient
```

### loaddata fails with "Duplicate entry" or "IntegrityError"

This usually means content types or auth permissions have conflicts:
```bash
python manage.py shell -c "
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
ContentType.objects.all().delete()
Permission.objects.all().delete()
"
python manage.py loaddata full_backup.json
```

### loaddata fails with "Could not load contenttypes.ContentType"

Exclude content types from the export and let Django recreate them:
```bash
# Re-export without contenttypes and auth.permission
python manage.py dumpdata --natural-foreign --natural-primary --indent=2 \
    --exclude contenttypes --exclude auth.permission \
    -o full_backup_no_ct.json

# On MariaDB:
python manage.py migrate
python manage.py loaddata full_backup_no_ct.json
```

### "Data too long for column" errors

SQLite doesn't enforce VARCHAR length limits but MariaDB does. If a field has data longer than the model's `max_length`:
```bash
# Find the offending data
python manage.py shell -c "
from django.db import connection
# Example: check company_name lengths
from customers.models import Customer
long_names = Customer.objects.extra(where=['LENGTH(company_name) > 100'])
for c in long_names:
    print(f'ID {c.id}: {len(c.company_name)} chars - {c.company_name[:50]}...')
"
```

Fix by truncating or increasing the field's `max_length` before migrating.

---

## Post-Migration Checklist

- [ ] MariaDB installed and running
- [ ] Database and user created
- [ ] `.env` updated with `DB_ENGINE=mariadb` and credentials
- [ ] `python manage.py migrate` ran successfully
- [ ] `python manage.py loaddata` completed without errors
- [ ] Data counts verified (users, customers, proposals, funnel)
- [ ] Application starts without errors
- [ ] Multi-user access tested (no more "database is locked")
- [ ] Old `db.sqlite3` file backed up
- [ ] MariaDB added to server backup schedule (e.g., `mysqldump` cron job)

---

## Recommended: Setup MariaDB Auto-Backup

Add a daily backup cron job:

```bash
sudo mkdir -p /var/backups/mariadb

# Create backup script
sudo tee /usr/local/bin/backup_mi_crm_db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/var/backups/mariadb
FILENAME="mi_crm_$(date +%Y%m%d_%H%M%S).sql.gz"
mysqldump -u mi_crm_user -p'YOUR_PASSWORD' mi_crm | gzip > "$BACKUP_DIR/$FILENAME"
# Keep only last 14 days
find "$BACKUP_DIR" -name "mi_crm_*.sql.gz" -mtime +14 -delete
EOF

sudo chmod +x /usr/local/bin/backup_mi_crm_db.sh

# Add to crontab (runs daily at 2 AM)
echo "0 2 * * * /usr/local/bin/backup_mi_crm_db.sh" | sudo tee -a /var/spool/cron/crontabs/root
```

---

## Summary

| Step | Action | Time |
|------|--------|------|
| 1-3 | Install MariaDB + create database | 5 min |
| 4 | Export SQLite data | 1 min |
| 5 | Stop application | 10 sec |
| 6-7 | Update .env + run migrations | 2 min |
| 8 | Load data into MariaDB | 1-5 min |
| 9-11 | Verify + start + test | 5 min |
| **Total downtime** | | **~10-15 minutes** |
