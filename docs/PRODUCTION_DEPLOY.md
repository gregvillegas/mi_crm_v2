# MiCRM — Production Deployment Guide

**Target environment:** Ubuntu 22.04 LTS · Apache 2.4 · MariaDB 10.6 · Python 3.10+

---

## Table of Contents

1. [Overview of Changes Made](#1-overview-of-changes-made)
2. [Pre-Deployment: Back Up SQLite Data](#2-pre-deployment-back-up-sqlite-data)
3. [Server Prerequisites](#3-server-prerequisites)
4. [Deploy the Application](#4-deploy-the-application)
5. [Configure .env on the Server](#5-configure-env-on-the-server)
6. [Import Backup Data into MariaDB](#6-import-backup-data-into-mariadb)
7. [Set Up SSL with Let's Encrypt](#7-set-up-ssl-with-lets-encrypt)
8. [Post-Deployment Checklist](#8-post-deployment-checklist)
9. [Subsequent Deploys (Updates)](#9-subsequent-deploys-updates)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Overview of Changes Made

The following files were modified from the development version to prepare for production:

| File | Change |
|---|---|
| `requirements.txt` | Added `mysqlclient==2.2.6` (MariaDB driver) and `python-decouple==3.8` (env vars) |
| `crm_project/settings.py` | Removed PostgreSQL, added MariaDB, moved all secrets to env vars via `python-decouple`, added production security headers |
| `apache_crm.conf` | Added HTTP→HTTPS redirect, SSL config, security headers, WSGI tuning, media upload protection |
| `.env.example` | Template for all required environment variables |
| `.gitignore` | Ensures `.env` and `db.sqlite3` are never committed |
| `deploy.sh` | Automated install and update script |

---

## 2. Pre-Deployment: Back Up SQLite Data

Run these commands **on your local development machine** before copying files to the server.

```bash
cd /private/var/www/mi_crm
source venv/bin/activate   # or however you activate your local venv

# Export all app data to a JSON fixture (excludes framework-internal tables)
python manage.py dumpdata \
  --natural-foreign \
  --natural-primary \
  --exclude=contenttypes \
  --exclude=auth.permission \
  --indent=2 \
  -o db_backup.json

echo "Backup created: db_backup.json ($(wc -l < db_backup.json) lines)"
```

Keep `db_backup.json` safe — you will upload it to the server and import it into MariaDB in Step 6.

> **Note:** `db_backup.json` is listed in `.gitignore` and will not be committed. Transfer it manually via `scp` or `rsync`.

---

## 3. Server Prerequisites

SSH into your Ubuntu 22.04 server and run:

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
    python3 python3-pip python3-venv python3-dev \
    apache2 libapache2-mod-wsgi-py3 \
    mariadb-server mariadb-client libmariadb-dev pkg-config \
    git curl ufw certbot python3-certbot-apache
```

Enable required Apache modules:

```bash
sudo a2enmod wsgi rewrite headers ssl expires
sudo systemctl restart apache2
```

Secure MariaDB:

```bash
sudo mysql_secure_installation
# Answer: set root password, remove anonymous users, disallow remote root login,
# remove test database, reload privilege tables — all Yes.
```

Create the database and user:

```bash
sudo mysql -u root -p
```

```sql
CREATE DATABASE mi_crm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'mi_crm_user'@'localhost' IDENTIFIED BY 'YOUR_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON mi_crm.* TO 'mi_crm_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

## 4. Deploy the Application

**From your local machine**, copy the project to the server:

```bash
rsync -avz --progress \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='venv' \
  --exclude='db.sqlite3' \
  --exclude='staticfiles' \
  --exclude='media' \
  /private/var/www/mi_crm/ \
  your_user@your_server_ip:/var/www/mi_crm/
```

Also copy the backup file:

```bash
scp db_backup.json your_user@your_server_ip:/var/www/mi_crm/
```

**On the server**, set up the virtual environment and install dependencies:

```bash
cd /var/www/mi_crm

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip wheel
pip install -r requirements.txt
```

---

## 5. Configure .env on the Server

Create the `.env` file from the example template:

```bash
cp /var/www/mi_crm/.env.example /var/www/mi_crm/.env
nano /var/www/mi_crm/.env
```

Fill in every value. The minimum required settings for production:

```ini
# Generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY=your-generated-secret-key-here

DEBUG=False
ALLOWED_HOSTS=crm.microimageph.com

DB_ENGINE=mariadb
DB_NAME=mi_crm
DB_USER=mi_crm_user
DB_PASSWORD=YOUR_STRONG_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=3306

EMAIL_HOST_USER=crm_sales@microimageph.com
EMAIL_HOST_PASSWORD=your-email-password

REDMINE_API_KEY=your-redmine-api-key

# IMPORTANT: Set this to your server's actual domain or IP — used to build
# absolute URLs in campaign emails (unsubscribe and interested buttons).
# Without this, email links will be broken and point to localhost.
SITE_URL=https://crm.microimageph.com

CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://crm.microimageph.com
```

Lock down permissions on the `.env` file:

```bash
sudo chown root:www-data /var/www/mi_crm/.env
sudo chmod 640 /var/www/mi_crm/.env
```

---

## 6. Import Backup Data into MariaDB

This is the core data migration step. Run in order:

```bash
cd /var/www/mi_crm
source venv/bin/activate

# Step 1: Create all tables from Django migrations
python manage.py migrate --noinput

# Step 2: Load the SQLite data dump into MariaDB
python manage.py loaddata db_backup.json

# Step 3: Verify the import
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
print(f'Users imported: {User.objects.count()}')
from customers.models import Customer
print(f'Customers imported: {Customer.objects.count()}')
"
```

> **If `loaddata` fails with integrity errors**, the most common cause is content types or site IDs being out of sync. Run:
> ```bash
> python manage.py migrate --run-syncdb
> python manage.py loaddata db_backup.json
> ```
> If it still fails, add `--exclude=contenttypes --exclude=auth.permission` to your `dumpdata` (already done in Step 2) and ensure the backup was created without those tables.

Collect static files:

```bash
python manage.py collectstatic --noinput
```

---

## 7. Set Up SSL with Let's Encrypt

```bash
sudo certbot --apache -d crm.microimageph.com
```

Certbot will automatically update the Apache config with your SSL certificate paths and set up auto-renewal. Test renewal:

```bash
sudo certbot renew --dry-run
```

Verify auto-renewal is scheduled:

```bash
sudo systemctl status certbot.timer
```

---

## 8. Post-Deployment Checklist

Run all of these on the server before going live:

```bash
cd /var/www/mi_crm
source venv/bin/activate

# Django deployment check (reports any security issues)
python manage.py check --deploy

# Set correct ownership for writable directories
sudo chown -R www-data:www-data /var/www/mi_crm/media
sudo chown -R www-data:www-data /var/www/mi_crm/staticfiles

# Install and enable Apache site config
sudo cp /var/www/mi_crm/apache_crm.conf /etc/apache2/sites-available/mi_crm.conf
sudo a2ensite mi_crm.conf
sudo a2dissite 000-default.conf  # disable default site
sudo apache2ctl configtest       # must say "Syntax OK"
sudo systemctl reload apache2

# Configure firewall
sudo ufw allow OpenSSH
sudo ufw allow 'Apache Full'
sudo ufw enable
sudo ufw status

# Create the first admin user
python manage.py createsuperuser
```

Verify the site is live:

```bash
curl -I https://crm.microimageph.com
# Expect: HTTP/2 200 (or 301 from HTTP)
```

---

## 9. Subsequent Deploys (Updates)

After the initial setup, use the `--update` flag for fast re-deploys:

```bash
# 1. From local machine: push new code
rsync -avz --progress \
  --exclude='.git' --exclude='venv' --exclude='__pycache__' \
  --exclude='db.sqlite3' --exclude='staticfiles' --exclude='media' \
  /private/var/www/mi_crm/ \
  your_user@your_server_ip:/var/www/mi_crm/

# 2. On the server: run update script
cd /var/www/mi_crm
./deploy.sh --update
```

The `--update` flag runs: `pip install` → `migrate` → `collectstatic` → permission fix → Apache reload.

---

## 10. Troubleshooting

### Apache 500 error after deploy

```bash
# Check Apache error log
sudo tail -50 /var/log/apache2/mi_crm_error.log

# Check Django can load settings manually
source /var/www/mi_crm/venv/bin/activate
cd /var/www/mi_crm
python manage.py check
```

### `No module named 'MySQLdb'`

```bash
source /var/www/mi_crm/venv/bin/activate
pip install mysqlclient
```

If `mysqlclient` fails to compile:

```bash
sudo apt-get install -y libmariadb-dev libmariadb-dev-compat
pip install mysqlclient
```

### `Access denied for user 'mi_crm_user'@'localhost'`

```bash
sudo mysql -u root -p
# Then re-run the GRANT statement from Step 3
GRANT ALL PRIVILEGES ON mi_crm.* TO 'mi_crm_user'@'localhost';
FLUSH PRIVILEGES;
```

### Static files returning 404

```bash
python manage.py collectstatic --noinput --clear
sudo chown -R www-data:www-data /var/www/mi_crm/staticfiles
sudo systemctl reload apache2
```

### `.env` variables not being read

Verify python-decouple is installed in the venv and the `.env` file is in `/var/www/mi_crm/` (the `BASE_DIR`):

```bash
source /var/www/mi_crm/venv/bin/activate
python -c "from decouple import config; print(config('DEBUG'))"
```

### `django.db.utils.OperationalError: (2002, "Can't connect to server")`

```bash
sudo systemctl status mariadb
sudo systemctl start mariadb
sudo systemctl enable mariadb
```

---

*Generated for MiCRM — Micro Image International Corp.*
