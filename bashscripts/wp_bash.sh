#!/usr/bin/env bash
#
# wp-manager.sh — Install / Harden / Uninstall (Purge) WordPress via interactive menu
# - INSTALL: LAMP + WordPress (subdir /var/www/html/wordpress) with port checks & prompts
# - HARDEN : Built-in hardening (no external modules; no Let’s Encrypt)
# - UNINSTALL (PURGE): Integrated modes: content-only | complete | apps-only
#
set -Eeuo pipefail

#######################################
# Colors & UI helpers
#######################################
if command -v tput >/dev/null 2>&1 && [[ -t 1 ]]; then
  GREEN="$(tput setaf 2)"; RED="$(tput setaf 1)"; YELLOW="$(tput setaf 3)"; BOLD="$(tput bold)"; RESET="$(tput sgr0)"
else
  GREEN=""; RED=""; YELLOW=""; BOLD=""; RESET=""
fi
print_green(){ echo -e "${GREEN}$*${RESET}"; }
print_red()  { echo -e "${RED}$*${RESET}"  ; }
print_yellow(){ echo -e "${YELLOW}$*${RESET}"; }
log()   { echo -e "${GREEN}[*]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[!]${RESET} $*" >&2; }
error() { echo -e "${RED}[x]${RESET} $*" >&2; }

trap 'error "Failed at line $LINENO"; exit 1' ERR

#######################################
# Root check & logging
#######################################
require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    error "This script must be run as root."
    exit 1
  fi
}
LOG_FILE="/var/log/wp_manager.log"
setup_logging() {
  mkdir -p "$(dirname "$LOG_FILE")"
  touch "$LOG_FILE"
  exec > >(tee -a "$LOG_FILE") 2>&1
  echo -e "\n===== $(date -u +"%Y-%m-%dT%H:%M:%SZ") :: wp-manager start ====="
}
cleanup() {
  local code=$?
  echo "===== $(date -u +"%Y-%m-%dT%H:%M:%SZ") :: wp-manager end (exit $code) ====="
}
trap cleanup EXIT

#######################################
# Generic helpers
#######################################
command_exists(){ command -v "$1" >/dev/null 2>&1; }
confirm(){ read -r -p "${1} [y/N]: " ans; [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]]; }
run(){ eval "$@"; }

#######################################
# Port check helpers
#######################################
check_port_status() {
  local port=$1
  if command -v ss &> /dev/null; then
    ss -tpln | grep -q ":$port"
  elif command -v netstat &> /dev/null; then
    netstat -tpln | grep -q ":$port"
  else
    print_red "Neither ss nor netstat is installed. Cannot check port status."
    exit 1
  fi
}
check_ports_80_443() {
  print_green "🔍 Checking port 80 (HTTP)..."
  if check_port_status 80; then
    print_green "✅ Port 80 is OPEN."
  else
    print_red "❌ Port 80 is CLOSED."
  fi
  print_green "🔍 Checking port 443 (HTTPS)..."
  if check_port_status 443; then
    print_green "✅ Port 443 is OPEN."
  else
    print_red "❌ Port 443 is CLOSED."
  fi
}

#######################################
# Paths / config
#######################################
APACHE_ROOT_DEFAULT="/var/www/html"
WP_DIR_DEFAULT="${APACHE_ROOT_DEFAULT}/wordpress"
WP_CONFIG_NEW_PATH_DEFAULT="/var/www"

#######################################
# LAMP + WordPress install functions
#######################################
install_prereqs() {
  print_green "🔄 Updating package index and upgrading installed packages..."
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

  print_green "📦 Installing prerequisites..."
  apt-get install -y software-properties-common curl ca-certificates lsb-release apt-transport-https
}
install_php() {
  print_green "➕ Adding PHP repository (Ondřej PPA)..."
  add-apt-repository -y ppa:ondrej/php
  apt-get update -y

  print_green "🐘 Installing PHP 7.4 and extensions..."
  # NOTE: PHP 7.4 is EOL; adjust to a supported version if you prefer.
  apt-get install -y php7.4 php7.4-mysql php7.4-curl php7.4-gd php7.4-mbstring php7.4-xml php7.4-zip php7.4-xmlrpc libapache2-mod-php7.4
}
install_mysql() {
  print_green "🛢️ Installing MySQL server..."
  DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server
  print_yellow "⚠️ Running mysql_secure_installation interactively. Follow prompts."
  mysql_secure_installation
}
configure_mysql_wp() {
  local name="$1" user="$2" pass="$3"
  print_green "🛠️ Configuring MySQL for WordPress..."
  mysql -u root <<EOF
CREATE DATABASE IF NOT EXISTS \`$name\`;
CREATE USER IF NOT EXISTS '$user'@'localhost' IDENTIFIED BY '$pass';
GRANT ALL PRIVILEGES ON \`$name\`.* TO '$user'@'localhost';
FLUSH PRIVILEGES;
EOF
}
install_apache() {
  print_green "🌐 Installing Apache web server..."
  apt-get install -y apache2
  a2enmod rewrite
  systemctl enable apache2
  systemctl restart apache2
}
download_wordpress() {
  local apache_root="$1"; local wp_dir="$2"
  print_green "⬇️ Downloading WordPress..."
  if [[ ! -d "$wp_dir" ]]; then
    pushd /tmp >/dev/null
    curl -fSLo latest.tar.gz https://wordpress.org/latest.tar.gz
    tar xzvf latest.tar.gz
    mv wordpress "$apache_root/"
    rm -f latest.tar.gz
    popd >/dev/null
  else
    print_yellow "WordPress directory already exists at $wp_dir — skipping download."
  fi

  print_green "🔒 Setting permissions..."
  chown -R www-data:www-data "$wp_dir"
  find "$wp_dir" -type d -exec chmod 755 {} \;
  find "$wp_dir" -type f -exec chmod 644 {} \;
}
configure_wp_config() {
  local wp_dir="$1" db_name="$2" db_user="$3" db_pass="$4"
  print_green "⚙️ Configuring wp-config.php..."
  pushd "$wp_dir" >/dev/null
  [[ -f wp-config.php ]] || cp wp-config-sample.php wp-config.php

  sed -i "s/'DB_NAME', 'database_name_here'/'DB_NAME', '$db_name'/g" wp-config.php
  sed -i "s/'DB_USER', 'username_here'/'DB_USER', '$db_user'/g" wp-config.php
  sed -i "s/'DB_PASSWORD', 'password_here'/'DB_PASSWORD', '$db_pass'/g" wp-config.php
  sed -i "s/'DB_HOST', 'localhost'/'DB_HOST', 'localhost'/g" wp-config.php

  # Insert fresh salts
  SALTS=$(curl -fsSL https://api.wordpress.org/secret-key/1.1/salt/) || SALTS=""
  if [[ -n "$SALTS" ]]; then
    sed -i "/AUTH_KEY/d;/SECURE_AUTH_KEY/d;/LOGGED_IN_KEY/d;/NONCE_KEY/d;/AUTH_SALT/d;/SECURE_AUTH_SALT/d;/LOGGED_IN_SALT/d;/NONCE_SALT/d" wp-config.php
    printf "%s\n" "$SALTS" >> wp-config.php
  fi
  popd >/dev/null
}
restart_apache(){ print_green "🔁 Restarting Apache..."; systemctl restart apache2; }

#######################################
# HARDEN — Embedded functions (no external modules)
#######################################

# 1) Firewall: prefer ufw (Debian/Ubuntu); fallback to firewalld; otherwise iptables rules minimal
configure_firewall() {
  print_green "🧱 Configuring firewall..."
  if command_exists ufw; then
    :
  else
    apt-get update -y && apt-get install -y ufw || true
  fi

  if command_exists ufw; then
    ufw --force reset >/dev/null 2>&1 || true
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow OpenSSH || ufw allow 22 || true
    # Apache profiles if available; else open 80/443
    if ufw app list 2>/dev/null | grep -q "Apache Full"; then
      ufw allow "Apache Full"
    else
      ufw allow 80/tcp
      ufw allow 443/tcp
    fi
    yes | ufw enable >/dev/null 2>&1 || ufw enable || true
    ufw status verbose || true
  elif command_exists firewall-cmd; then
    # firewalld path (RHEL-like)
    systemctl enable --now firewalld || true
    firewall-cmd --permanent --add-service=http || firewall-cmd --permanent --add-port=80/tcp
    firewall-cmd --permanent --add-service=https || firewall-cmd --permanent --add-port=443/tcp
    firewall-cmd --permanent --add-service=ssh || firewall-cmd --permanent --add-port=22/tcp
    firewall-cmd --reload || true
    firewall-cmd --list-all || true
  else
    warn "No ufw/firewalld found; applying basic iptables (volatile) rules…"
    iptables -P INPUT DROP || true
    iptables -P FORWARD DROP || true
    iptables -P OUTPUT ACCEPT || true
    iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT || true
    iptables -A INPUT -p tcp --dport 22 -j ACCEPT || true
    iptables -A INPUT -p tcp --dport 80 -j ACCEPT || true
    iptables -A INPUT -p tcp --dport 443 -j ACCEPT || true
    iptables -A INPUT -i lo -j ACCEPT || true
  fi
}

# 2) Fail2Ban with Apache jails (auth, bots, XML-RPC, WP-specific)
setup_fail2ban() {
  print_green "🛡️ Installing & configuring Fail2Ban…"
  apt-get update -y && apt-get install -y fail2ban || true
  systemctl enable fail2ban || true

  mkdir -p /etc/fail2ban/jail.d
  cat >/etc/fail2ban/jail.d/wordpress-apache.conf <<'JAIL'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
backend = systemd

[apache-auth]
enabled = true
port    = http,https
logpath = /var/log/apache2/*error.log
maxretry = 5

[apache-badbots]
enabled = true
port    = http,https
logpath = /var/log/apache2/*access.log
maxretry = 2

[apache-noscript]
enabled = true
port    = http,https
logpath = /var/log/apache2/*error.log
maxretry = 2

[apache-overflows]
enabled = true
port    = http,https
logpath = /var/log/apache2/*error.log
maxretry = 2

# Basic XML-RPC brute mitigation
[apache-xmlrpc]
enabled = true
port    = http,https
logpath = /var/log/apache2/*access.log
maxretry = 10
findtime = 10m
bantime  = 1h
filter   = apache-xmlrpc

# WordPress login attempts (works with standard /wp-login.php)
[wordpress-login]
enabled = true
port    = http,https
logpath = /var/log/apache2/*access.log
maxretry = 10
findtime = 10m
bantime  = 1h
filter   = wordpress-login
JAIL

  # filters
  mkdir -p /etc/fail2ban/filter.d
  cat >/etc/fail2ban/filter.d/apache-xmlrpc.conf <<'FILTER'
[Definition]
failregex = ^<HOST> - .* "POST /xmlrpc\.php HTTP/.*" 200
ignoreregex =
FILTER

  cat >/etc/fail2ban/filter.d/wordpress-login.conf <<'FILTER'
[Definition]
# Count repeated POSTs to wp-login.php with 200/302/403
failregex = ^<HOST> - .* "(GET|POST) /wp-login\.php HTTP/.*" (200|302|403)
ignoreregex =
FILTER

  systemctl restart fail2ban || true
  systemctl status fail2ban --no-pager || true
}

# 3) Apache hardening: headers, server tokens, methods, directory perms
secure_apache() {
  print_green "🔐 Applying Apache hardening…"
  apt-get install -y apache2 || true

  a2enmod headers >/dev/null 2>&1 || true
  a2enmod rewrite >/dev/null 2>&1 || true
  a2enmod security2 >/dev/null 2>&1 || true || echo

  # security.conf tweaks
  local secconf="/etc/apache2/conf-available/security.conf"
  if [[ -f "$secconf" ]]; then
    sed -i 's/^\s*ServerTokens.*/ServerTokens Prod/i' "$secconf" || true
    sed -i 's/^\s*ServerSignature.*/ServerSignature Off/i' "$secconf" || true
  else
    cat > /etc/apache2/conf-available/security.conf <<'SEC'
ServerTokens Prod
ServerSignature Off
TraceEnable Off
SEC
  fi

  # headers
  local headers_conf="/etc/apache2/conf-available/hardening-headers.conf"
  cat > "$headers_conf" <<'HDR'
<IfModule mod_headers.c>
  Header always set X-Content-Type-Options "nosniff"
  Header always set X-Frame-Options "SAMEORIGIN"
  Header always set Referrer-Policy "strict-origin-when-cross-origin"
  Header always set X-XSS-Protection "1; mode=block"
  Header always set Permissions-Policy "geolocation=(), camera=(), microphone=()"
</IfModule>
HDR
  a2enconf hardening-headers >/dev/null 2>&1 || true
  a2enconf security >/dev/null 2>&1 || true

  # keepalive & request size (conservative)
  local mpm="/etc/apache2/mods-available/mpm_prefork.conf"
  if [[ -f "$mpm" ]]; then
    sed -i 's/^\s*MaxRequestWorkers.*/MaxRequestWorkers 150/i' "$mpm" || true
    sed -i 's/^\s*KeepAliveTimeout.*/KeepAliveTimeout 5/i' "$mpm" || true
  fi

  # Limit methods at root level
  local methods="/etc/apache2/conf-available/hardening-methods.conf"
  cat > "$methods" <<'METH'
<Directory "/var/www/">
  <LimitExcept GET POST HEAD>
    Require all denied
  </LimitExcept>
</Directory>
METH
  a2enconf hardening-methods >/dev/null 2>&1 || true

  systemctl reload apache2 || systemctl restart apache2 || true
}

# 4) .htaccess rules for WordPress
deploy_htaccess() {
  local wp_dir="$1"
  print_green "📄 Deploying secure .htaccess to ${wp_dir}…"

  # Core + hardening rules. Non-destructive: backup if exists.
  if [[ -f "${wp_dir}/.htaccess" ]]; then
    cp -a "${wp_dir}/.htaccess" "${wp_dir}/.htaccess.bak.$(date +%s)"
  fi

  cat > "${wp_dir}/.htaccess" <<'HT'
# BEGIN WordPress
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteBase /wordpress/
RewriteRule ^index\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /wordpress/index.php [L]
</IfModule>
# END WordPress

# Disable directory listing
Options -Indexes

# Restrict sensitive files
<FilesMatch "(^\.|wp-config\.php|readme\.html|license\.txt|composer\.(json|lock))">
  Require all denied
</FilesMatch>

# Protect wp-includes
<IfModule mod_rewrite.c>
RewriteRule ^wp-admin/includes/ - [F,L]
RewriteRule !^wp-includes/ - [S=3]
RewriteRule ^wp-includes/[^/]+\.php$ - [F,L]
RewriteRule ^wp-includes/js/tinymce/langs/.+\.php - [F,L]
RewriteRule ^wp-includes/theme-compat/ - [F,L]
</IfModule>

# Limit access to xmlrpc.php (allow from localhost only)
<Files xmlrpc.php>
  Require ip 127.0.0.1 ::1
</Files>

# Block PHP execution in uploads
<Directory "/var/www/html/wordpress/wp-content/uploads/">
  <FilesMatch "\.php$">
    Require all denied
  </FilesMatch>
</Directory>
HT

  chown www-data:www-data "${wp_dir}/.htaccess" || true
  chmod 0644 "${wp_dir}/.htaccess" || true
}

# 5) Move wp-config.php safely outside webroot (with stub include)
move_wp_config() {
  local wp_dir="$1"
  local target_dir="$2"   # e.g. /var/www
  print_green "📦 Moving wp-config.php to ${target_dir}…"

  mkdir -p "$target_dir"
  local src="${wp_dir}/wp-config.php"
  local dst="${target_dir}/wp-config.php"

  if [[ ! -f "$src" ]]; then
    error "wp-config.php not found in ${wp_dir}"
    return 1
  fi

  # Backup original
  cp -a "$src" "${src}.bak.$(date +%s)"

  # Move real config and create a stub loader so WP can find it even if not one-level parent
  mv -f "$src" "$dst"
  chown root:root "$dst" || true
  chmod 0640 "$dst" || true

  cat > "$src" <<STUB
<?php
// Loader stub — keep outside-webroot config in a custom path.
define('WP_CONFIG_EXTERNAL', '${dst}');
if (file_exists(WP_CONFIG_EXTERNAL)) {
    require_once WP_CONFIG_EXTERNAL;
} else {
    die('wp-config external file not found.');
}
STUB

  chown www-data:www-data "$src" || true
  chmod 0640 "$src" || true
}

# 6) Generate a simple security report
generate_log_report() {
  local out="/var/log/wp_security_report.txt"
  print_green "📝 Generating security report at ${out}…"
  {
    echo "=== WordPress Security Report ==="
    date -u +"%Y-%m-%dT%H:%M:%SZ"
    echo

    echo "[Apache]"
    apache2 -v 2>/dev/null || httpd -v 2>/dev/null || echo "Apache not found"
    echo
    echo "[Loaded Modules]"
    apache2ctl -M 2>/dev/null || httpd -M 2>/dev/null || true

    echo
    echo "[UFW Status]"
    ufw status verbose 2>&1 || echo "UFW not available"

    echo
    echo "[Fail2Ban Status]"
    systemctl is-active fail2ban 2>/dev/null || true
    fail2ban-client status 2>/dev/null || true
    fail2ban-client status apache-auth 2>/dev/null || true
    fail2ban-client status wordpress-login 2>/dev/null || true
    fail2ban-client status apache-xmlrpc 2>/dev/null || true

    echo
    echo "[/var/www perms]"
    namei -l /var/www/html 2>/dev/null || true
  } > "$out"
  chmod 0644 "$out" || true
}

#######################################
# HARDEN workflow (calls embedded functions)
#######################################
harden_wordpress() {
  local apache_root="${1:-$APACHE_ROOT_DEFAULT}"
  local wp_dir="${2:-$WP_DIR_DEFAULT}"
  local wp_config_new_path="${3:-$WP_CONFIG_NEW_PATH_DEFAULT}"

  print_green "🔧 Starting WordPress hardening (built-in)…"

  print_green "[*] Configuring firewall..."
  configure_firewall

  print_green "[*] Installing and configuring Fail2Ban..."
  setup_fail2ban

  print_green "[*] Securing Apache..."
  secure_apache

  print_green "[*] Deploying secure .htaccess..."
  deploy_htaccess "$wp_dir"

  print_green "[*] Moving wp-config.php to a secure location..."
  move_wp_config "$wp_dir" "$wp_config_new_path"

  print_green "[*] Generating and exporting log report..."
  generate_log_report

  restart_apache
  print_green "✅ Hardening complete."
}

#######################################
# UNINSTALL (PURGE) — Embedded wp-purge logic
#######################################
# package manager & services detect
detect_pm_services() {
  PKG=""
  if command_exists apt-get; then
    PKG="apt"
  elif command_exists dnf; then
    PKG="dnf"
  elif command_exists yum; then
    PKG="yum"
  else
    error "Unsupported system: no apt, dnf, or yum found."
    exit 1
  fi

  APACHE_SVC=""
  if systemctl list-unit-files | grep -q '^apache2\.service'; then APACHE_SVC="apache2"
  elif systemctl list-unit-files | grep -q '^httpd\.service'; then APACHE_SVC="httpd"; fi

  SQL_SVC=""
  if systemctl list-unit-files | grep -q '^mysql\.service'; then SQL_SVC="mysql"
  elif systemctl list-unit-files | grep -q '^mariadb\.service'; then SQL_SVC="mariadb"; fi
}

mysql_exec_embedded() {
  local sql="$1" root_pw="$2"
  if [[ -z "$root_pw" ]]; then
    mysql -u root --protocol=socket --batch --raw --execute "$sql"
  else
    local tmp; tmp="$(mktemp)"; chmod 600 "$tmp"
    cat > "$tmp" <<EOF
[client]
user=root
password=${root_pw}
protocol=socket
EOF
    mysql --defaults-extra-file="$tmp" --batch --raw --execute "$sql"
    rm -f "$tmp"
  fi
}

mysqldump_embedded() {
  local db="$1" out="$2" root_pw="$3"
  if [[ -z "$root_pw" ]]; then
    mysqldump -u root --single-transaction --routines --triggers "$db" > "$out"
  else
    local tmp; tmp="$(mktemp)"; chmod 600 "$tmp"
    cat > "$tmp" <<EOF
[client]
user=root
password=${root_pw}
protocol=socket
EOF
    mysqldump --defaults-extra-file="$tmp" --single-transaction --routines --triggers "$db" > "$out" || true
    rm -f "$tmp"
  fi
}

uninstall_menu() {
  detect_pm_services

  # Auto-detect WP dir
  local WP_DIR
  for cand in /var/www/html/wordpress /var/www/wordpress /srv/www/wordpress /var/www/html; do
    if [[ -f "$cand/wp-config.php" || -d "$cand/wp-admin" ]]; then WP_DIR="$cand"; break; fi
  done
  [[ -z "${WP_DIR:-}" ]] && WP_DIR="/var/www/html/wordpress"

  echo
  echo "${BOLD}Choose uninstall mode:${RESET}"
  echo "  1) Remove WordPress content only (files + DB/user; keep apps)"
  echo "  2) Complete delete (apps + configs + WP files + DB/user)"
  echo "  3) Remove apps only (keep WP files + DB/user)"
  echo
  read -r -p "Enter 1/2/3: " choice
  local MODE
  case "$choice" in
    1) MODE="content-only" ;;
    2) MODE="complete" ;;
    3) MODE="apps-only" ;;
    *) error "Invalid selection."; exit 2;;
  esac

  local needs_db=false needs_files=false remove_packages=false purge_packages=false
  case "$MODE" in
    content-only) needs_db=true; needs_files=true; remove_packages=false; purge_packages=false ;;
    complete)     needs_db=true; needs_files=true; remove_packages=true;  purge_packages=true  ;;
    apps-only)    needs_db=false; needs_files=false; remove_packages=true; purge_packages=false ;;
  esac

  local DB_NAME="" DB_USER="" MYSQL_ROOT_PASSWORD="" BACKUP_SQL=""
  if $needs_db; then
    read -r -p "Enter the database name to delete: " DB_NAME
    read -r -p "Enter the database user to delete: " DB_USER
    read -r -s -p "Enter the MySQL root password (leave empty for socket auth): " MYSQL_ROOT_PASSWORD; echo
    read -r -p "Optional: path to backup SQL before delete (leave empty to skip): " BACKUP_SQL

    case "${DB_NAME}" in
      mysql|sys|performance_schema|information_schema)
        error "Refusing to drop critical database '${DB_NAME}'."
        exit 3;;
    esac
    [[ "${DB_USER}" == "root" ]] && { error "Refusing to drop user 'root'."; exit 3; }
  fi

  echo
  warn "${BOLD}Plan:${RESET}"
  case "$MODE" in
    content-only)
      echo " - Delete WordPress files under '${WP_DIR}'"
      echo " - Drop DB '${DB_NAME}' and user '${DB_USER}'@'localhost'"
      echo " - Keep Apache/MySQL/PHP installed"
      ;;
    complete)
      echo " - Remove Apache/MySQL/PHP (purge configs/data)"
      echo " - Delete WordPress files under '${WP_DIR}'"
      echo " - Drop DB '${DB_NAME}' and user '${DB_USER}'@'localhost'"
      ;;
    apps-only)
      echo " - Remove Apache/MySQL/PHP packages (keep files + DB)"
      ;;
  esac
  echo
  confirm "Proceed?" || { warn "Aborted."; return; }

  # Stop services if removing packages
  if [[ -n "${APACHE_SVC:-}" && $remove_packages == true ]]; then
    log "Stopping Apache (${APACHE_SVC})..."
    run "systemctl stop ${APACHE_SVC} || true"
  fi
  if [[ -n "${SQL_SVC:-}" && $remove_packages == true ]]; then
    log "Stopping database service (${SQL_SVC})..."
    run "systemctl stop ${SQL_SVC} || true"
  fi

  # Package changes
  if $remove_packages; then
    case "$PKG" in
      apt)
        if $purge_packages; then
          log "Purging Apache..."
          run "apt-get remove --purge -y apache2 apache2-utils apache2-bin || true"
          log "Purging MySQL/MariaDB..."
          run "apt-get remove --purge -y mysql-server mysql-client mariadb-server mariadb-client mysql-common mariadb-common || true"
          log "Purging PHP..."
          run "apt-get remove --purge -y 'php*' 'libapache2-mod-php*' || true"
        else
          log "Removing Apache (keeping configs)..."
          run "apt-get remove -y apache2 apache2-utils apache2-bin || true"
          log "Removing MySQL/MariaDB (keeping configs/data)..."
          run "apt-get remove -y mysql-server mysql-client mariadb-server mariadb-client || true"
          log "Removing PHP (keeping configs)..."
          run "apt-get remove -y 'php*' 'libapache2-mod-php*' || true"
        fi
        log "Autoremove/autoclean..."
        run "apt-get -y autoremove || true"
        run "apt-get -y autoclean || true"
        if $purge_packages; then
          log "Removing data/config dirs (MySQL/MariaDB)…"
          run "rm -rf /etc/mysql /var/lib/mysql /var/lib/mariadb || true"
          # Optional: remove Ondrej PPA if present
          if command_exists add-apt-repository && grep -qi 'ppa.launchpadcontent.net/ondrej/php' /etc/apt/sources.list.d/*.list 2>/dev/null; then
            log "Removing PPA:ondrej/php..."
            run "add-apt-repository --remove -y ppa:ondrej/php || true"
          fi
        fi
        ;;
      dnf|yum)
        PM="$PKG -y"
        log "Removing Apache/MySQL/PHP packages..."
        run "$PM remove httpd httpd-tools || true"
        run "$PM remove mysql-server mariadb-server mariadb || true"
        run "$PM remove 'php*' php-cli php-fpm mod_php || true"
        if [[ "$PKG" == "dnf" ]]; then
          run "dnf autoremove -y || true"
          run "dnf clean all || true"
        else
          run "yum autoremove -y || true"
          run "yum clean all || true"
        fi
        if $purge_packages; then
          log "Removing data/config dirs (MySQL/MariaDB)…"
          run "rm -rf /etc/my.cnf /etc/mysql /var/lib/mysql /var/lib/mariadb || true"
        fi
        ;;
    esac
  fi

  # Delete WordPress files
  if [[ "$MODE" != "apps-only" ]]; then
    log "Deleting WordPress files..."
    if [[ -d "${WP_DIR}" ]]; then
      run "rm -rf --one-file-system -- '${WP_DIR}'"
    else
      warn "WordPress directory '${WP_DIR}' not found; skipping."
    fi
    for f in /var/www/html/wp-config.php /var/www/html/wp-config-sample.php; do
      [[ -e "$f" ]] && run "rm -f -- '$f'"
    done
    if [[ -d /var/www/html ]]; then
      log "Resetting ownership/perms on /var/www/html..."
      run "chown -R root:root /var/www/html"
      run "find /var/www/html -type d -exec chmod 755 {} +"
      run "find /var/www/html -type f -exec chmod 644 {} +"
    fi
  fi

  # DB actions
  if [[ "$MODE" != "apps-only" ]]; then
    if [[ -n "${DB_NAME:-}" && -n "${DB_USER:-}" ]]; then
      if [[ -n "${BACKUP_SQL:-}" ]]; then
        log "Backing up database '${DB_NAME}' to '${BACKUP_SQL}'..."
        mysqldump_embedded "$DB_NAME" "$BACKUP_SQL" "${MYSQL_ROOT_PASSWORD:-}"
      fi
      log "Dropping database '${DB_NAME}' and user '${DB_USER}'@'localhost'..."
      mysql_exec_embedded "
        SET sql_notes=0;
        DROP DATABASE IF EXISTS \`${DB_NAME}\`;
        DROP USER IF EXISTS '${DB_USER}'@'localhost';
        FLUSH PRIVILEGES;
      " "${MYSQL_ROOT_PASSWORD:-}"
    else
      warn "DB name/user not provided; skipping DB drop."
    fi
  fi

  log "Done. Uninstall mode '${MODE}' completed."
}

#######################################
# INSTALL workflow (uses your original prompts)
#######################################
install_menu() {
  check_ports_80_443
  echo
  read -r -p "Do you want to continue with the script execution? (yes/no): " user_choice
  if [[ "$user_choice" != "yes" && "$user_choice" != "y" ]]; then
    print_red "❌ Script execution aborted by the user."
    exit 0
  fi

  read -r -p "Enter your server IP address: " server_ip
  read -r -p "Enter your database name: " db_name
  read -r -p "Enter your database username: " db_user
  read -r -s -p "Enter your database password: " db_password; echo
  read -r -s -p "Enter the WordPress database password (same as above unless different): " wp_password; echo
  [[ -z "$wp_password" ]] && wp_password="$db_password"

  local APACHE_ROOT="$APACHE_ROOT_DEFAULT"
  local WP_DIR="$WP_DIR_DEFAULT"

  install_prereqs
  install_php
  install_mysql
  configure_mysql_wp "$db_name" "$db_user" "$db_password"
  install_apache
  download_wordpress "$APACHE_ROOT" "$WP_DIR"
  configure_wp_config "$WP_DIR" "$db_name" "$db_user" "$db_password"
  restart_apache

  print_green "✅ WordPress installation is complete."
  echo "🌐 Visit: http://$server_ip/wordpress"
  echo "📌 If using a domain, ensure your DNS points to $server_ip"
  echo "🛠️ Finish setup in the browser interface."
}

#######################################
# HARDEN workflow (menu wrapper)
#######################################
harden_menu() {
  local wp_dir="$WP_DIR_DEFAULT"
  local wp_cfg_path="$WP_CONFIG_NEW_PATH_DEFAULT"

  read -r -p "WordPress directory? [${wp_dir}]: " in; wp_dir="${in:-$wp_dir}"
  read -r -p "Secure path to move wp-config.php? [${wp_cfg_path}]: " in; wp_cfg_path="${in:-$wp_cfg_path}"

  harden_wordpress "$APACHE_ROOT_DEFAULT" "$wp_dir" "$wp_cfg_path"
  print_green "🗒️ A security report was saved to /var/log/wp_security_report.txt"
}

#######################################
# MAIN MENU
#######################################
main_menu() {
  echo
  echo "${BOLD}WordPress Manager — choose an action:${RESET}"
  echo "  1) Install WordPress (LAMP + WP)"
  echo "  2) Harden existing WordPress (built-in)"
  echo "  3) Uninstall / Purge WordPress (interactive modes)"
  echo "  4) Exit"
  echo
  read -r -p "Enter 1/2/3/4: " sel
  case "$sel" in
    1) install_menu ;;
    2) harden_menu ;;
    3) uninstall_menu ;;
    4) echo "Bye."; exit 0 ;;
    *) error "Invalid selection."; exit 2 ;;
  esac
}

#######################################
# Entry
#######################################
require_root
setup_logging
main_menu
