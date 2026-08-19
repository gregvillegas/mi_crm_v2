#!/usr/bin/env bash
# ==============================================================================
# deploy.sh — Production deployment script for MiCRM on Ubuntu 22.04
# ==============================================================================
# Run this script on the PRODUCTION SERVER as a user with sudo privileges.
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh            # Full first-time install
#   ./deploy.sh --update   # Pull latest code and restart (subsequent deploys)
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# Configuration — adjust these if your paths or domain differ
# ------------------------------------------------------------------------------
PROJECT_DIR="/var/www/mi_crm"
VENV_DIR="$PROJECT_DIR/venv"
APACHE_CONF_SRC="$PROJECT_DIR/apache_crm.conf"
APACHE_CONF_DEST="/etc/apache2/sites-available/mi_crm.conf"
PYTHON="python3"
PIP="$VENV_DIR/bin/pip"
MANAGE="$VENV_DIR/bin/python $PROJECT_DIR/manage.py"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ==============================================================================
# UPDATE MODE — fast re-deploy after a code push
# ==============================================================================
if [[ "${1:-}" == "--update" ]]; then
    info "Running update deploy..."

    cd "$PROJECT_DIR"

    info "Installing/updating Python dependencies..."
    $PIP install --quiet -r requirements.txt

    info "Running database migrations..."
    $MANAGE migrate --noinput

    info "Collecting static files..."
    $MANAGE collectstatic --noinput --clear

    info "Setting file permissions..."
    sudo chown -R www-data:www-data "$PROJECT_DIR/media" "$PROJECT_DIR/staticfiles"
    sudo chmod 600 "$PROJECT_DIR/.env"

    info "Reloading Apache..."
    sudo systemctl reload apache2

    info "Update deploy complete."
    exit 0
fi

# ==============================================================================
# FULL INSTALL MODE
# ==============================================================================
info "Starting full production install..."

# ------------------------------------------------------------------------------
# 1. System packages
# ------------------------------------------------------------------------------
info "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3 python3-pip python3-venv python3-dev \
    apache2 libapache2-mod-wsgi-py3 \
    mariadb-server mariadb-client \
    libmariadb-dev pkg-config \
    rsync git curl ufw \
    certbot python3-certbot-apache

# ------------------------------------------------------------------------------
# 2. Apache modules
# ------------------------------------------------------------------------------
info "Enabling Apache modules..."
sudo a2enmod wsgi rewrite headers ssl expires
sudo a2dissite 000-default.conf 2>/dev/null || true

# ------------------------------------------------------------------------------
# 3. MariaDB setup
# ------------------------------------------------------------------------------
info "Securing MariaDB and creating database..."
warning "You will be prompted to set a MariaDB root password and secure the installation."
sudo mysql_secure_installation

# Read DB credentials from .env if it already exists, otherwise prompt
if [[ -f "$PROJECT_DIR/.env" ]]; then
    DB_NAME=$(grep '^DB_NAME' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '[:space:]')
    DB_USER=$(grep '^DB_USER' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '[:space:]')
    DB_PASS=$(grep '^DB_PASSWORD' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '[:space:]')
else
    warning ".env not found at $PROJECT_DIR/.env"
    read -rp "Enter MariaDB database name [mi_crm]: " DB_NAME
    DB_NAME=${DB_NAME:-mi_crm}
    read -rp "Enter MariaDB username [mi_crm_user]: " DB_USER
    DB_USER=${DB_USER:-mi_crm_user}
    read -rsp "Enter MariaDB password: " DB_PASS
    echo
fi

sudo mysql -u root -p <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';

GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';

FLUSH PRIVILEGES;
SQL
info "Database '$DB_NAME' and user '$DB_USER' created."

# ------------------------------------------------------------------------------
# 4. Python virtual environment
# ------------------------------------------------------------------------------
info "Setting up Python virtual environment..."
$PYTHON -m venv "$VENV_DIR"
$PIP install --quiet --upgrade pip wheel

# ------------------------------------------------------------------------------
# 5. Install Python dependencies
# ------------------------------------------------------------------------------
info "Installing Python dependencies..."
$PIP install --quiet -r "$PROJECT_DIR/requirements.txt"

# ------------------------------------------------------------------------------
# 6. .env file check
# ------------------------------------------------------------------------------
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    warning ".env file not found. Creating from .env.example — YOU MUST EDIT IT BEFORE CONTINUING."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    error "Edit $PROJECT_DIR/.env with your real values, then re-run this script."
fi

# ------------------------------------------------------------------------------
# 7. Django setup
# ------------------------------------------------------------------------------
info "Running database migrations..."
$MANAGE migrate --noinput

info "Collecting static files..."
$MANAGE collectstatic --noinput

info "Checking Django deployment readiness..."
$MANAGE check --deploy 2>&1 | grep -v "^System check" || true

# ------------------------------------------------------------------------------
# 8. File permissions
# ------------------------------------------------------------------------------
info "Setting file permissions..."
sudo chown -R www-data:www-data "$PROJECT_DIR/media"
sudo chown -R www-data:www-data "$PROJECT_DIR/staticfiles"
sudo chown root:www-data "$PROJECT_DIR/.env"
sudo chmod 640 "$PROJECT_DIR/.env"
sudo chmod -R 755 "$PROJECT_DIR"

# ------------------------------------------------------------------------------
# 9. Apache site configuration
# ------------------------------------------------------------------------------
info "Installing Apache configuration..."
sudo cp "$APACHE_CONF_SRC" "$APACHE_CONF_DEST"
sudo a2ensite mi_crm.conf
sudo apache2ctl configtest && sudo systemctl reload apache2

# ------------------------------------------------------------------------------
# 10. Firewall (UFW)
# ------------------------------------------------------------------------------
info "Configuring UFW firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 'Apache Full'
sudo ufw --force enable
sudo ufw status

# ------------------------------------------------------------------------------
# Done
# ------------------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Full deploy complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Next steps:"
echo "  1. Verify the site:    curl -I http://crm.microimageph.com"
echo "  2. Set up SSL:         sudo certbot --apache -d crm.microimageph.com"
echo "  3. Create superuser:   $MANAGE createsuperuser"
echo "  4. Import backup data (see PRODUCTION_DEPLOY.md for full instructions)"
echo ""
