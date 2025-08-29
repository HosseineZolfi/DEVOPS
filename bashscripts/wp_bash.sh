#!/usr/bin/env bash
# -*- bash -*-
#
# wp-manager.sh — Install / Harden / Uninstall (Purge) WordPress via interactive, staged menu
# Now with: per-stage confirmations, optional undo, and on-screen progress bars
#
# - INSTALL: LAMP + WordPress (subdir /var/www/html/wordpress) with port checks & prompts
# - HARDEN : Built-in hardening (no external modules; no Let’s Encrypt)
# - UNINSTALL (PURGE): content-only | complete | apps-only — staged with best-effort undo
#
# DISCLAIMER: "Undo" is best-effort. Package operations and firewall rules can be hard to
# perfectly revert across distros or previously-customized hosts. This tool attempts safe,
# minimal, *documented* reversions for exactly-just-applied changes. Always review prompts
# and keep backups for production systems.

# ================================
# Preflight (colors, UI, utils)
# ================================
USE_TTY=0
if [ -t 1 ]; then USE_TTY=1; fi

_ansi() { if [ "$USE_TTY" -eq 1 ]; then printf "\033[%sm" "$1"; fi; }
GREEN="$(_ansi 32)"; RED="$(_ansi 31)"; YELLOW="$(_ansi 33)"; CYAN="$(_ansi 36)"; BOLD="$(_ansi 1)"; RESET="$(_ansi 0)"

print_green(){ printf "%b%s%b\n" "$GREEN" "$1" "$RESET"; }
print_red()  { printf "%b%s%b\n" "$RED"   "$1" "$RESET" >&2; }
print_yellow(){ printf "%b%s%b\n" "$YELLOW" "$1" "$RESET"; }
print_cyan() { printf "%b%s%b\n" "$CYAN"  "$1" "$RESET"; }

log()  { printf "%b[*]%b %s\n" "$GREEN" "$RESET" "$1"; }
warn() { printf "%b[!]%b %s\n" "$YELLOW" "$RESET" "$1" >&2; }
error(){ printf "%b[x]%b %s\n" "$RED" "$RESET" "$1" >&2; }

command_exists(){ command -v "$1" >/dev/null 2>&1; }

confirm(){ 
  local prompt="$1"
  local ans
  read -r -p "$prompt [y/N]: " ans
  ans="${ans,,}"
  [[ "$ans" == "y" || "$ans" == "yes" ]]
}

run(){ # run "cmd string" ; respects '|| true' in the passed string
  local cmd="$1"
  log "\$ $cmd"
  bash -c "$cmd"
  return $?
}

# ================================
# Root check & logging
# ================================
require_root(){
  if [ "$EUID" -ne 0 ]; then
    error "This script must be run as root."
    exit 1
  fi
}

LOG_FILE="/var/log/wp_manager.log"
setup_logging(){
  mkdir -p "$(dirname "$LOG_FILE")"
  # Print start banner before hooking tee (to both console & file)
  local start_ts
  start_ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "" | tee -a "$LOG_FILE" >/dev/null
  echo "===== ${start_ts} :: wp-manager start =====" | tee -a "$LOG_FILE"
  # Duplicate stdout/stderr to file
  exec > >(tee -a "$LOG_FILE") 2>&1
}
cleanup(){
  local code=$?
  local end_ts
  end_ts="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "===== ${end_ts} :: wp-manager end (exit ${code}) ====="
}
trap cleanup EXIT

# ================================
# Progress bar helpers
# ================================
_bar(){
  local pct=$1 width=${2:-36}
  (( pct < 0 )) && pct=0
  (( pct > 100 )) && pct=100
  local filled=$(( width * pct / 100 ))
  printf "[%s%s] %3d%%" "$(printf '#%.0s' $(seq 1 $filled))" "$(printf ' -%.0s' $(seq 1 $((width - filled))))" "$pct" | sed 's/ -/-/g'
}
show_bar(){
  local label="$1" pct="$2"
  local line
  line="$(printf "%b%-28s%b %s" "$CYAN" "$label" "$RESET" "$(_bar "$pct")")"
  if [ "$USE_TTY" -eq 1 ]; then
    printf "\r%s" "$line"
    # no newline
  else
    printf "%s\n" "$line"
  fi
}
end_bar(){ if [ "$USE_TTY" -eq 1 ]; then printf "\n"; fi; }

# ================================
# Stage framework
# ================================
# We keep step metadata in arrays
reset_steps(){ STEPS_NAME=(); STEPS_DO=(); STEPS_UNDO=(); STEPS_NOTE=(); }
add_step(){ # name, do_fn, undo_fn, [note]
  STEPS_NAME+=("$1"); STEPS_DO+=("$2"); STEPS_UNDO+=("$3"); STEPS_NOTE+=("${4:-}")
}
call_if_defined(){ # $1=function_name
  local fn="$1"
  if [ -n "$fn" ] && declare -F "$fn" >/dev/null 2>&1; then "$fn"; else return 0; fi
}
run_stages(){ # "Title"
  local title="$1"
  echo
  printf "%b%s%b\n" "$BOLD" "$title" "$RESET"
  local total="${#STEPS_NAME[@]}"
  local i
  for (( i=0; i<total; i++ )); do
    local idx=$((i+1))
    local name="${STEPS_NAME[$i]}"
    local dofn="${STEPS_DO[$i]}"
    local undofn="${STEPS_UNDO[$i]}"
    local note="${STEPS_NOTE[$i]}"

    echo
    print_cyan "— Stage ${idx}/${total}: ${name}"
    [ -n "$note" ] && print_yellow "  $note"
    if ! confirm "Proceed with this stage?"; then
      if confirm "Skip this stage and continue to next?"; then
        continue
      else
        warn "Aborted by user."
        exit 0
      fi
    fi

    local start_ts elapsed
    start_ts=$(date +%s)
    show_bar "$name" 0

    if call_if_defined "$dofn"; then
      show_bar "$name" 100; end_bar
    else
      end_bar
      error "Command failed during stage '$name'."
      if [ -n "$undofn" ] && confirm "Attempt to undo this stage now?"; then
        if call_if_defined "$undofn"; then
          print_yellow "Reverted (best-effort)."
        else
          error "Undo failed."
        fi
      fi
      exit 1
    fi

    elapsed=$(( $(date +%s) - start_ts ))
    log "Stage completed in ~${elapsed}s"

    while true; do
      local ans
      read -r -p "Next action — [C]ontinue, [U]ndo this stage, [A]bort: " ans
      ans="${ans,,}"
      if [[ -z "$ans" || "$ans" =~ ^(c|cont|continue|y|yes)$ ]]; then
        break
      elif [[ "$ans" =~ ^(u|undo)$ ]]; then
        if [ -n "$undofn" ]; then
          print_yellow "Undoing this stage…"
          if call_if_defined "$undofn"; then
            print_green "Stage undone (best-effort)."
          else
            error "Undo failed."
          fi
        else
          warn "No automatic undo is available for this stage."
        fi
        if confirm "Proceed to the next stage?"; then
          break
        else
          warn "Aborted by user after undo."
          exit 0
        fi
      elif [[ "$ans" =~ ^(a|abort|q|quit)$ ]]; then
        warn "Aborted by user."
        exit 0
      fi
    done
  done
  print_green "✅ All selected stages completed."
}

# ================================
# Port checks
# ================================
check_port_status(){ # port
  local port="$1"
  if command_exists ss; then
    ss -tpln | grep -qE ":${port}\b"
  elif command_exists netstat; then
    netstat -tpln 2>/dev/null | grep -qE ":${port}\b"
  else
    print_red "Neither ss nor netstat is installed. Cannot check port status."
    return 1
  fi
}
check_ports_80_443(){
  print_green "🔍 Checking port 80 (HTTP)…"
  if check_port_status 80; then print_green "✅ Port 80 is OPEN."; else print_red "❌ Port 80 is CLOSED."; fi
  print_green "🔍 Checking port 443 (HTTPS)…"
  if check_port_status 443; then print_green "✅ Port 443 is OPEN."; else print_red "❌ Port 443 is CLOSED."; fi
}

# ================================
# Paths / state
# ================================
APACHE_ROOT_DEFAULT="/var/www/html"
WP_DIR_DEFAULT="${APACHE_ROOT_DEFAULT}/wordpress"
WP_CONFIG_NEW_PATH_DEFAULT="/var/www"
STATE_DIR="/var/lib/wp-manager"
TRASH_ROOT="/var/tmp/wp-manager-trash"
mkdir -p "$STATE_DIR" "$TRASH_ROOT"
BACKUPS_FILE="${STATE_DIR}/backups.list"        # lines: src|backup
RUN_STATE_DOWNLOADED_WP_DIR=0

backup_file(){ # path
  local path="$1"
  if [ ! -e "$path" ]; then return 0; fi
  local ts b
  ts=$(date +%s)
  b="${path}.bak.${ts}"
  cp -p "$path" "$b" || return 1
  echo "${path}|${b}" >> "$BACKUPS_FILE"
}
restore_latest_backup(){ # path
  local path="$1"
  if [ ! -e "$BACKUPS_FILE" ]; then return 1; fi
  local line
  line="$(grep -F "^${path}|" "$BACKUPS_FILE" 2>/dev/null | tail -n 1)"
  [ -z "$line" ] && return 1
  local bak="${line#*|}"
  [ -f "$bak" ] || return 1
  cp -f "$bak" "$path"
}

# ================================
# LAMP + WordPress install fns
# ================================
install_prereqs(){
  print_green "🔄 Updating package index and upgrading installed packages…"
  run "apt-get update -y" || return 1
  run "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y" || return 1
  print_green "📦 Installing prerequisites…"
  run "apt-get install -y software-properties-common curl ca-certificates lsb-release apt-transport-https" || return 1
}
undo_install_prereqs(){
  print_yellow "Best-effort: running autoremove/autoclean…"
  run "apt-get -y autoremove || true"
  run "apt-get -y autoclean || true"
}

install_php(){
  print_green "➕ Adding PHP repository (Ondřej PPA)…"
  run "add-apt-repository -y ppa:ondrej/php" || return 1
  run "apt-get update -y" || return 1
  print_green "🐘 Installing PHP 7.4 and extensions…"
  run "apt-get install -y php7.4 php7.4-mysql php7.4-curl php7.4-gd php7.4-mbstring php7.4-xml php7.4-zip php7.4-xmlrpc libapache2-mod-php7.4" || return 1
}
undo_install_php(){
  print_yellow "Removing PHP packages (best-effort)…"
  run "apt-get remove --purge -y 'php7.4*' 'libapache2-mod-php7.4' || true"
  run "apt-get -y autoremove || true"
}

install_mysql(){
  print_green "🛢️ Installing MySQL server…"
  run "DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server" || return 1
  print_yellow "⚠️ Running mysql_secure_installation interactively. Follow prompts."
  run "mysql_secure_installation || true"
}
undo_install_mysql(){
  print_yellow "Removing MySQL server (best-effort)…"
  run "systemctl stop mysql || true"
  run "apt-get remove --purge -y mysql-server mysql-client mariadb-server mariadb-client || true"
  run "apt-get -y autoremove || true"
}

configure_mysql_wp(){ # name user pw
  local name="$1" user="$2" pw="$3"
  print_green "🛠️ Configuring MySQL for WordPress…"
  run "mysql -u root <<'EOF'
CREATE DATABASE IF NOT EXISTS ${name};
CREATE USER IF NOT EXISTS '${user}'@'localhost' IDENTIFIED BY '${pw}';
GRANT ALL PRIVILEGES ON ${name}.* TO '${user}'@'localhost';
FLUSH PRIVILEGES;
EOF" || return 1
}
undo_configure_mysql_wp(){ # name user
  local name="$1" user="$2"
  print_yellow "Dropping created DB/user (best-effort)…"
  run "mysql -u root <<'EOF'
SET sql_notes=0;
DROP DATABASE IF EXISTS ${name};
DROP USER IF EXISTS '${user}'@'localhost';
FLUSH PRIVILEGES;
EOF || true"
}

install_apache(){
  print_green "🌐 Installing Apache web server…"
  run "apt-get install -y apache2" || return 1
  run "a2enmod rewrite" || return 1
  run "systemctl enable apache2" || return 1
  run "systemctl restart apache2" || return 1
}
undo_install_apache(){
  print_yellow "Removing Apache (best-effort)…"
  run "systemctl stop apache2 || true"
  run "apt-get remove -y apache2 apache2-utils apache2-bin || true"
  run "apt-get -y autoremove || true"
}

download_wordpress(){ # apache_root wp_dir
  local apache_root="$1" wp_dir="$2"
  print_green "⬇️ Downloading WordPress…"
  if [ ! -d "$wp_dir" ]; then
    local td
    td="$(mktemp -d)"
    run "curl -fSLo '${td}/latest.tar.gz' https://wordpress.org/latest.tar.gz" || { rm -rf "$td"; return 1; }
    run "tar xzvf '${td}/latest.tar.gz' -C '${td}'" || { rm -rf "$td"; return 1; }
    run "mv '${td}/wordpress' '${apache_root}/'" || { rm -rf "$td"; return 1; }
    rm -rf "$td"
    RUN_STATE_DOWNLOADED_WP_DIR=1
    echo "created" > "${wp_dir}/.wp_manager_created"
  else
    print_yellow "WordPress directory already exists at ${wp_dir} — skipping download."
  fi
  print_green "🔒 Setting permissions…"
  run "chown -R www-data:www-data '${wp_dir}'"
  run "find '${wp_dir}' -type d -exec chmod 755 {} \\;"
  run "find '${wp_dir}' -type f -exec chmod 644 {} \\;"
}
undo_download_wordpress(){ # wp_dir
  local wp_dir="$1"
  if [ -f "${wp_dir}/.wp_manager_created" ]; then
    print_yellow "Removing freshly created WordPress directory…"
    run "rm -rf --one-file-system -- '${wp_dir}' || true"
  else
    warn "WordPress dir pre-existed; not removing."
  fi
}

_fetch_salts(){
  curl -fsSL --max-time 10 "https://api.wordpress.org/secret-key/1.1/salt/" || true
}

configure_wp_config(){ # wp_dir db_name db_user db_pass
  local wp_dir="$1" db_name="$2" db_user="$3" db_pass="$4"
  print_green "⚙️ Configuring wp-config.php…"
  local wp_cfg="${wp_dir}/wp-config.php"
  local wp_sample="${wp_dir}/wp-config-sample.php"
  if [ ! -f "$wp_cfg" ] && [ -f "$wp_sample" ]; then
    cp "$wp_sample" "$wp_cfg"
  fi
  backup_file "$wp_cfg"
  # Replace DB params
  sed -i \
    -e "s/'DB_NAME', 'database_name_here'/'DB_NAME', '${db_name}'/g" \
    -e "s/'DB_USER', 'username_here'/'DB_USER', '${db_user}'/g" \
    -e "s/'DB_PASSWORD', 'password_here'/'DB_PASSWORD', '${db_pass}'/g" \
    -e "s/'DB_HOST', 'localhost'/'DB_HOST', 'localhost'/g" \
    "$wp_cfg"
  # Remove old salts
  sed -i "/AUTH_KEY\|SECURE_AUTH_KEY\|LOGGED_IN_KEY\|NONCE_KEY\|AUTH_SALT\|SECURE_AUTH_SALT\|LOGGED_IN_SALT\|NONCE_SALT/d" "$wp_cfg"
  # Append fresh salts
  local salts
  salts="$(_fetch_salts)"
  if [ -n "$salts" ]; then
    printf "\n%s\n" "$salts" >> "$wp_cfg"
  fi
}
undo_configure_wp_config(){ # wp_dir
  local wp_dir="$1" wp_cfg="${wp_dir}/wp-config.php"
  if restore_latest_backup "$wp_cfg"; then
    print_yellow "Restored ${wp_cfg} from backup."
  else
    warn "No backup tracked; leaving current wp-config.php as is."
  fi
}

restart_apache(){
  print_green "🔁 Restarting Apache…"
  run "systemctl restart apache2 || systemctl restart httpd || true"
}

# ================================
# HARDEN — Embedded functions
# ================================
configure_firewall(){
  print_green "🧱 Configuring firewall…"
  if ! command_exists ufw && ! command_exists firewall-cmd; then
    run "apt-get update -y && apt-get install -y ufw || true"
  fi
  if command_exists ufw; then
    local snap="${STATE_DIR}/ufw.status.before"
    ufw status verbose > "$snap" 2>&1 || true
    run "ufw --force reset >/dev/null 2>&1 || true"
    run "ufw default deny incoming"
    run "ufw default allow outgoing"
    run "ufw allow OpenSSH || ufw allow 22 || true"
    if ufw app list 2>/dev/null | grep -q 'Apache Full'; then
      run "ufw allow 'Apache Full'"
    else
      run "ufw allow 80/tcp"
      run "ufw allow 443/tcp"
    fi
    run "yes | ufw enable >/dev/null 2>&1 || ufw enable || true"
    run "ufw status verbose || true"
  elif command_exists firewall-cmd; then
    run "systemctl enable --now firewalld || true"
    run "firewall-cmd --permanent --add-service=http || firewall-cmd --permanent --add-port=80/tcp"
    run "firewall-cmd --permanent --add-service=https || firewall-cmd --permanent --add-port=443/tcp"
    run "firewall-cmd --permanent --add-service=ssh || firewall-cmd --permanent --add-port=22/tcp"
    run "firewall-cmd --reload || true"
    run "firewall-cmd --list-all || true"
  else
    warn "No ufw/firewalld found; applying basic iptables (volatile) rules…"
    run "iptables -P INPUT DROP || true"
    run "iptables -P FORWARD DROP || true"
    run "iptables -P OUTPUT ACCEPT || true"
    run "iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT || true"
    run "iptables -A INPUT -p tcp --dport 22 -j ACCEPT || true"
    run "iptables -A INPUT -p tcp --dport 80 -j ACCEPT || true"
    run "iptables -A INPUT -p tcp --dport 443 -j ACCEPT || true"
    run "iptables -A INPUT -i lo -j ACCEPT || true"
  fi
}
undo_configure_firewall(){
  if command_exists ufw; then
    print_yellow "Disabling ufw and restoring prior state snapshot if any…"
    run "ufw --force disable || true"
    local snap="${STATE_DIR}/ufw.status.before"
    if [ -f "$snap" ]; then
      warn "Automatic re-apply from snapshot is not supported; please reconfigure manually if needed."
    fi
  elif command_exists firewall-cmd; then
    print_yellow "Reloading firewalld defaults (best-effort)…"
    run "firewall-cmd --reload || true"
  else
    warn "No firewall tool available to undo."
  fi
}

setup_fail2ban(){
  print_green "🛡️ Installing & configuring Fail2Ban…"
  run "apt-get update -y && apt-get install -y fail2ban || true"
  run "systemctl enable fail2ban || true"
  mkdir -p /etc/fail2ban/jail.d /etc/fail2ban/filter.d
  cat > /etc/fail2ban/jail.d/wordpress-apache.conf <<'CONF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
backend = systemd

[apache-auth]
enabled = true
port = http,https
logpath = /var/log/apache2/*error.log
maxretry = 5

[apache-badbots]
enabled = true
port = http,https
logpath = /var/log/apache2/*access.log
maxretry = 2

[apache-noscript]
enabled = true
port = http,https
logpath = /var/log/apache2/*error.log
maxretry = 2

[apache-overflows]
enabled = true
port = http,https
logpath = /var/log/apache2/*error.log
maxretry = 2

# Basic XML-RPC brute mitigation
[apache-xmlrpc]
enabled = true
port = http,https
logpath = /var/log/apache2/*access.log
maxretry = 10
findtime = 10m
bantime = 1h
filter = apache-xmlrpc

# WordPress login attempts (works with standard /wp-login.php)
[wordpress-login]
enabled = true
port = http,https
logpath = /var/log/apache2/*access.log
maxretry = 10
findtime = 10m
bantime = 1h
filter = wordpress-login
CONF

  cat > /etc/fail2ban/filter.d/apache-xmlrpc.conf <<'CONF'
[Definition]
failregex = ^<HOST> - .* "POST /xmlrpc\.php HTTP/.*" 200
ignoreregex =
CONF

  cat > /etc/fail2ban/filter.d/wordpress-login.conf <<'CONF'
[Definition]
# Count repeated POSTs to wp-login.php with 200/302/403
failregex = ^<HOST> - .* "(GET|POST) /wp-login\.php HTTP/.*" (200|302|403)
ignoreregex =
CONF

  run "systemctl restart fail2ban || true"
  run "systemctl status fail2ban --no-pager || true"
}
undo_setup_fail2ban(){
  print_yellow "Removing Fail2Ban jails and disabling service (best-effort)…"
  run "systemctl stop fail2ban || true"
  rm -f /etc/fail2ban/jail.d/wordpress-apache.conf \
        /etc/fail2ban/filter.d/apache-xmlrpc.conf \
        /etc/fail2ban/filter.d/wordpress-login.conf 2>/dev/null || true
  run "systemctl disable fail2ban || true"
}

secure_apache(){
  print_green "🔐 Applying Apache hardening…"
  run "apt-get install -y apache2 || true"
  run "a2enmod headers >/dev/null 2>&1 || true"
  run "a2enmod rewrite >/dev/null 2>&1 || true"
  run "a2enmod security2 >/dev/null 2>&1 || true"

  local secconf="/etc/apache2/conf-available/security.conf"
  if [ -f "$secconf" ]; then
    backup_file "$secconf"
    run "sed -i 's/^\\s*ServerTokens.*/ServerTokens Prod/i' '$secconf' || true"
    run "sed -i 's/^\\s*ServerSignature.*/ServerSignature Off/i' '$secconf' || true"
  else
    cat > "$secconf" <<'CONF'
ServerTokens Prod
ServerSignature Off
TraceEnable Off
CONF
  fi

  local headers_conf="/etc/apache2/conf-available/hardening-headers.conf"
  [ -f "$headers_conf" ] && backup_file "$headers_conf"
  cat > "$headers_conf" <<'CONF'
<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
Header always set X-Frame-Options "SAMEORIGIN"
Header always set Referrer-Policy "strict-origin-when-cross-origin"
Header always set X-XSS-Protection "1; mode=block"
Header always set Permissions-Policy "geolocation=(), camera=(), microphone=()"
</IfModule>
CONF
  run "a2enconf hardening-headers >/dev/null 2>&1 || true"
  run "a2enconf security >/dev/null 2>&1 || true"

  local mpm="/etc/apache2/mods-available/mpm_prefork.conf"
  if [ -f "$mpm" ]; then
    backup_file "$mpm"
    run "sed -i 's/^\\s*MaxRequestWorkers.*/MaxRequestWorkers 150/i' '$mpm' || true"
    run "sed -i 's/^\\s*KeepAliveTimeout.*/KeepAliveTimeout 5/i' '$mpm' || true"
  fi

  local methods="/etc/apache2/conf-available/hardening-methods.conf"
  [ -f "$methods" ] && backup_file "$methods"
  cat > "$methods" <<'CONF'
<Directory "/var/www/">
    <LimitExcept GET POST HEAD>
        Require all denied
    </LimitExcept>
</Directory>
CONF
  run "a2enconf hardening-methods >/dev/null 2>&1 || true"
  run "systemctl reload apache2 || systemctl restart apache2 || true"
}
undo_secure_apache(){
  print_yellow "Restoring Apache configs from backups where available…"
  if [ -f "$BACKUPS_FILE" ]; then
    awk -F'|' '/^\/etc\/apache2\// {print $1 "|" $2}' "$BACKUPS_FILE" | while IFS='|' read -r src bak; do
      [ -f "$bak" ] && cp -f "$bak" "$src"
    done
  fi
  run "a2disconf hardening-headers || true"
  run "a2disconf hardening-methods || true"
  run "systemctl reload apache2 || true"
}

deploy_htaccess(){ # wp_dir
  local wp_dir="$1" ht="${wp_dir}/.htaccess"
  print_green "📄 Deploying secure .htaccess to ${wp_dir}…"
  if [ -f "$ht" ]; then
    cp -p "$ht" "${wp_dir}/.htaccess.bak.$(date +%s)"
  fi
  cat > "$ht" <<'HT'
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
  if getent passwd www-data >/dev/null 2>&1 && getent group www-data >/dev/null 2>&1; then
    chown www-data:www-data "$ht" || true
  fi
  chmod 644 "$ht" || true
}
undo_deploy_htaccess(){ # wp_dir
  local wp_dir="$1" ht="${wp_dir}/.htaccess"
  local latest
  latest="$(ls -1 "${wp_dir}"/.htaccess.bak.* 2>/dev/null | tail -n 1)"
  if [ -n "$latest" ]; then
    print_yellow "Restoring .htaccess from ${latest}…"
    cp -f "$latest" "$ht"
  else
    warn "No .htaccess backup found to restore."
  fi
}

move_wp_config(){ # wp_dir target_dir
  local wp_dir="$1" target_dir="$2"
  print_green "📦 Moving wp-config.php to ${target_dir}…"
  mkdir -p "$target_dir"
  local src="${wp_dir}/wp-config.php"
  local dst="${target_dir}/wp-config.php"
  if [ ! -f "$src" ]; then
    error "wp-config.php not found in ${wp_dir}"
    return 1
  fi
  cp -p "$src" "${wp_dir}/wp-config.php.bak.$(date +%s)"
  mv "$src" "$dst"
  chown 0:0 "$dst" 2>/dev/null || true
  chmod 640 "$dst" || true
  cat > "${wp_dir}/wp-config.php" <<PHP
<?php // Loader stub — keep outside-webroot config in a custom path.
define('WP_CONFIG_EXTERNAL', '$dst');
if (file_exists(WP_CONFIG_EXTERNAL)) {
    require_once WP_CONFIG_EXTERNAL;
} else {
    die('wp-config external file not found.');
}
PHP
  if getent passwd www-data >/dev/null 2>&1 && getent group www-data >/dev/null 2>&1; then
    chown www-data:www-data "${wp_dir}/wp-config.php" || true
  fi
  chmod 640 "${wp_dir}/wp-config.php" || true
}
undo_move_wp_config(){ # wp_dir target_dir
  local wp_dir="$1" target_dir="$2"
  local real="${target_dir}/wp-config.php"
  local stub="${wp_dir}/wp-config.php"
  if [ -f "$real" ]; then
    print_yellow "Moving wp-config.php back inside WordPress dir…"
    mv -f "$real" "$stub"
  else
    warn "External wp-config.php not found; nothing to move back."
  fi
}

generate_log_report(){
  local out="/var/log/wp_security_report.txt"
  print_green "📝 Generating security report at ${out}…"
  {
    echo "=== WordPress Security Report ==="
    date -u +'%Y-%m-%dT%H:%M:%SZ'
    echo
    echo "[Apache]"
    (apache2 -v 2>/dev/null || httpd -v 2>/dev/null || echo 'Apache not found') | sed 's/^/  /'
    echo
    echo "[Loaded Modules]"
    (apache2ctl -M 2>/dev/null || httpd -M 2>/dev/null || true) | sed 's/^/  /'
    echo
    echo "[UFW Status]"
    (ufw status verbose 2>&1 || echo 'UFW not available') | sed 's/^/  /'
    echo
    echo "[Fail2Ban Status]"
    for cmd in \
      "systemctl is-active fail2ban 2>/dev/null || true" \
      "fail2ban-client status 2>/dev/null || true" \
      "fail2ban-client status apache-auth 2>/dev/null || true" \
      "fail2ban-client status wordpress-login 2>/dev/null || true" \
      "fail2ban-client status apache-xmlrpc 2>/dev/null || true"
    do bash -c "$cmd" | sed 's/^/  /'; done
    echo
    echo "[/var/www perms]"
    (namei -l /var/www/html 2>/dev/null || true) | sed 's/^/  /'
  } > "$out"
  chmod 644 "$out" || true
}
undo_generate_log_report(){
  local out="/var/log/wp_security_report.txt"
  [ -f "$out" ] && rm -f "$out"
}

# ================================
# HARDEN workflow
# ================================
harden_wordpress(){ # apache_root wp_dir wp_config_new_path
  local apache_root="$1" wp_dir="$2" wp_cfg_new="$3"
  print_green "🔧 Starting WordPress hardening (built-in)…"
  reset_steps
  add_step "Configure firewall" "configure_firewall" "undo_configure_firewall"
  add_step "Install & configure Fail2Ban" "setup_fail2ban" "undo_setup_fail2ban"
  add_step "Secure Apache" "secure_apache" "undo_secure_apache"
  add_step "Deploy secure .htaccess" "harden_deploy_htaccess" "harden_undo_deploy_htaccess"
  add_step "Move wp-config.php" "harden_move_wp_cfg" "harden_undo_move_wp_cfg"
  add_step "Generate security report" "generate_log_report" "undo_generate_log_report"
  add_step "Restart Apache" "restart_apache" "restart_apache"

  # small wrappers to pass args
  harden_deploy_htaccess(){ deploy_htaccess "$wp_dir"; }
  harden_undo_deploy_htaccess(){ undo_deploy_htaccess "$wp_dir"; }
  harden_move_wp_cfg(){ move_wp_config "$wp_dir" "$wp_cfg_new"; }
  harden_undo_move_wp_cfg(){ undo_move_wp_config "$wp_dir" "$wp_cfg_new"; }

  run_stages "Hardening Stages"
  print_green "✅ Hardening complete."
}

# ================================
# UNINSTALL (PURGE)
# ================================
PKG=""; APACHE_SVC=""; SQL_SVC=""
has_unit(){ systemctl list-unit-files | grep -qE "^${1}\.service"; }
detect_pm_services(){
  if command_exists apt-get; then PKG="apt"
  elif command_exists dnf; then PKG="dnf"
  elif command_exists yum; then PKG="yum"
  else error "Unsupported system: no apt, dnf, or yum found."; exit 1; fi

  if has_unit "apache2"; then APACHE_SVC="apache2"
  elif has_unit "httpd"; then APACHE_SVC="httpd"; fi

  if has_unit "mysql"; then SQL_SVC="mysql"
  elif has_unit "mariadb"; then SQL_SVC="mariadb"; fi
}

mysql_exec_embedded(){ # sql root_pw
  local sql="$1" root_pw="$2"
  if [ -z "$root_pw" ]; then
    run "mysql -u root --protocol=socket --batch --raw --execute \"$sql\""
  else
    local tf; tf="$(mktemp)"
    cat > "$tf" <<CONF
[client]
user=root
password=${root_pw}
protocol=socket
CONF
    run "mysql --defaults-extra-file='$tf' --batch --raw --execute \"$sql\""
    rm -f "$tf"
  fi
}
mysqldump_embedded(){ # db outpath root_pw
  local db="$1" outpath="$2" root_pw="$3"
  if [ -z "$root_pw" ]; then
    run "mysqldump -u root --single-transaction --routines --triggers ${db} > '${outpath}'"
  else
    local tf; tf="$(mktemp)"
    cat > "$tf" <<CONF
[client]
user=root
password=${root_pw}
protocol=socket
CONF
    run "mysqldump --defaults-extra-file='$tf' --single-transaction --routines --triggers ${db} > '${outpath}' || true"
    rm -f "$tf"
  fi
}

uninstall_menu(){
  detect_pm_services
  local wp_dir=""
  for cand in "/var/www/html/wordpress" "/var/www/wordpress" "/srv/www/wordpress" "/var/www/html"; do
    if { [ -d "$cand" ] && [ -d "$cand/wp-admin" ]; } || [ -f "$cand/wp-config.php" ]; then wp_dir="$cand"; break; fi
  done
  [ -z "$wp_dir" ] && wp_dir="/var/www/html/wordpress"

  echo
  printf "%bChoose uninstall mode:%b\n" "$BOLD" "$RESET"
  echo " 1) Remove WordPress content only (files + DB/user; keep apps)"
  echo " 2) Complete delete (apps + configs + WP files + DB/user)"
  echo " 3) Remove apps only (keep WP files + DB/user)"
  echo
  local choice MODE
  read -r -p "Enter 1/2/3: " choice
  case "$choice" in
    1) MODE="content-only" ;;
    2) MODE="complete" ;;
    3) MODE="apps-only" ;;
    *) error "Invalid selection."; exit 2 ;;
  esac

  local needs_db=0 remove_packages=0 purge_packages=0
  case "$MODE" in
    "content-only") needs_db=1 ;;
    "complete") needs_db=1; remove_packages=1; purge_packages=1 ;;
    "apps-only") remove_packages=1 ;;
  esac

  local DB_NAME="" DB_USER="" MYSQL_ROOT_PASSWORD="" BACKUP_SQL=""
  if [ "$needs_db" -eq 1 ]; then
    read -r -p "Enter the database name to delete: " DB_NAME
    read -r -p "Enter the database user to delete: " DB_USER
    read -r -s -p "Enter the MySQL root password (leave empty for socket auth): " MYSQL_ROOT_PASSWORD; echo
    read -r -p "Optional: path to backup SQL before delete (leave empty to skip): " BACKUP_SQL
    case "$DB_NAME" in
      mysql|sys|performance_schema|information_schema) error "Refusing to drop critical database '$DB_NAME'."; exit 3 ;;
    esac
    if [ "$DB_USER" = "root" ]; then error "Refusing to drop user 'root'."; exit 3; fi
  fi

  echo
  warn "${BOLD}Plan:${RESET}"
  case "$MODE" in
    "content-only")
      echo " - Delete WordPress files under '${wp_dir}'"
      echo " - Drop DB '${DB_NAME}' and user '${DB_USER}'@'localhost'"
      echo " - Keep Apache/MySQL/PHP installed"
      ;;
    "complete")
      echo " - Remove Apache/MySQL/PHP (purge configs/data)"
      echo " - Delete WordPress files under '${wp_dir}'"
      echo " - Drop DB '${DB_NAME}' and user '${DB_USER}'@'localhost'"
      ;;
    "apps-only")
      echo " - Remove Apache/MySQL/PHP packages (keep files + DB)"
      ;;
  esac
  echo

  if ! confirm "Proceed into staged uninstall now?"; then
    warn "Aborted."
    return
  fi

  local trash="${TRASH_ROOT}/$(date +%s)"
  mkdir -p "$trash"

  step_stop_services(){
    if [ -n "$APACHE_SVC" ]; then
      log "Stopping Apache (${APACHE_SVC})…"
      run "systemctl stop ${APACHE_SVC} || true"
    fi
    if [ -n "$SQL_SVC" ] && [ "$remove_packages" -eq 1 ]; then
      log "Stopping database service (${SQL_SVC})…"
      run "systemctl stop ${SQL_SVC} || true"
    fi
  }
  undo_stop_services(){
    [ -n "$APACHE_SVC" ] && run "systemctl start ${APACHE_SVC} || true"
    if [ -n "$SQL_SVC" ] && [ "$remove_packages" -eq 1 ]; then
      run "systemctl start ${SQL_SVC} || true"
    fi
  }

  step_remove_packages(){
    [ "$remove_packages" -eq 1 ] || return 0
    if [ "$PKG" = "apt" ]; then
      if [ "$purge_packages" -eq 1 ]; then
        log "Purging Apache…"; run "apt-get remove --purge -y apache2 apache2-utils apache2-bin || true"
        log "Purging MySQL/MariaDB…"; run "apt-get remove --purge -y mysql-server mysql-client mariadb-server mariadb-client mysql-common mariadb-common || true"
        log "Purging PHP…"; run "apt-get remove --purge -y 'php*' 'libapache2-mod-php*' || true"
      else
        log "Removing Apache (keeping configs)…"; run "apt-get remove -y apache2 apache2-utils apache2-bin || true"
        log "Removing MySQL/MariaDB (keeping configs/data)…"; run "apt-get remove -y mysql-server mysql-client mariadb-server mariadb-client || true"
        log "Removing PHP (keeping configs)…"; run "apt-get remove -y 'php*' 'libapache2-mod-php*' || true"
      fi
      log "Autoremove/autoclean…"
      run "apt-get -y autoremove || true"; run "apt-get -y autoclean || true"
      if [ "$purge_packages" -eq 1 ]; then
        log "Removing data/config dirs (MySQL/MariaDB)…"
        run "rm -rf /etc/mysql /var/lib/mysql /var/lib/mariadb || true"
      fi
      if command_exists add-apt-repository; then
        if grep -qi 'ppa.launchpadcontent.net/ondrej/php' /etc/apt/sources.list.d/*.list 2>/dev/null; then
          log "Removing PPA:ondrej/php…"
          run "add-apt-repository --remove -y ppa:ondrej/php || true"
        fi
      fi
    else
      local PMBIN="${PKG} -y"
      log "Removing Apache/MySQL/PHP packages…"
      run "${PMBIN} remove httpd httpd-tools || true"
      run "${PMBIN} remove mysql-server mariadb-server mariadb || true"
      run "${PMBIN} remove 'php*' php-cli php-fpm mod_php || true"
      if [ "$PKG" = "dnf" ]; then
        run "dnf autoremove -y || true"; run "dnf clean all || true"
      else
        run "yum autoremove -y || true"; run "yum clean all || true"
      fi
      if [ "$purge_packages" -eq 1 ]; then
        log "Removing data/config dirs (MySQL/MariaDB)…"
        run "rm -rf /etc/my.cnf /etc/mysql /var/lib/mysql /var/lib/mariadb || true"
      fi
    fi
  }
  undo_remove_packages(){
    warn "Package removals are not automatically re-installed by undo. Reinstall manually if needed."
  }

  step_delete_wp_files(){
    [ "$MODE" = "apps-only" ] && return 0
    if [ -e "$wp_dir" ]; then
      local dst="${trash}/wordpress-files"
      log "Moving '${wp_dir}' to trash '${dst}'…"
      mv "$wp_dir" "$dst"
    fi
    for f in "/var/www/html/wp-config.php" "/var/www/html/wp-config-sample.php"; do
      [ -f "$f" ] || continue
      local dst="${trash}/$(basename "$f")"
      mv "$f" "$dst"
    done
    if [ -d "/var/www/html" ]; then
      log "Resetting ownership/perms on /var/www/html…"
      run "chown -R root:root /var/www/html"
      run "find /var/www/html -type d -exec chmod 755 {} +"
      run "find /var/www/html -type f -exec chmod 644 {} +"
    fi
  }
  undo_delete_wp_files(){
    if [ -d "${trash}/wordpress-files" ]; then
      log "Restoring WordPress files from trash…"
      mv "${trash}/wordpress-files" "$wp_dir"
    fi
    for name in "wp-config.php" "wp-config-sample.php"; do
      if [ -f "${trash}/${name}" ]; then
        mv "${trash}/${name}" "/var/www/html/${name}"
      fi
    done
  }

  step_drop_db(){
    [ "$MODE" = "apps-only" ] && return 0
    if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
      warn "DB name/user not provided; skipping DB drop."
      return 0
    fi
    if [ -n "$BACKUP_SQL" ]; then
      log "Backing up database '${DB_NAME}' to '${BACKUP_SQL}'…"
      mysqldump_embedded "$DB_NAME" "$BACKUP_SQL" "$MYSQL_ROOT_PASSWORD" || true
    fi
    log "Dropping database '${DB_NAME}' and user '${DB_USER}'@'localhost'…"
    mysql_exec_embedded "
      SET sql_notes=0;
      DROP DATABASE IF EXISTS ${DB_NAME};
      DROP USER IF EXISTS '${DB_USER}'@'localhost';
      FLUSH PRIVILEGES;
    " "$MYSQL_ROOT_PASSWORD"
  }
  undo_drop_db(){
    if [ -n "$BACKUP_SQL" ] && [ -f "$BACKUP_SQL" ]; then
      warn "Attempting restore from backup SQL…"
      if [ -n "$MYSQL_ROOT_PASSWORD" ]; then
        local tf; tf="$(mktemp)"
        cat > "$tf" <<CONF
[client]
user=root
password=${MYSQL_ROOT_PASSWORD}
protocol=socket
CONF
        run "mysql --defaults-extra-file='$tf' < '${BACKUP_SQL}' || true"
        rm -f "$tf"
      else
        run "mysql -u root < '${BACKUP_SQL}' || true"
      fi
    else
      warn "No backup SQL available to restore."
    fi
  }

  reset_steps
  add_step "Stop services" "step_stop_services" "undo_stop_services"
  add_step "Remove packages" "step_remove_packages" "undo_remove_packages" "If chosen mode removes apps. Undo will NOT auto-reinstall packages."
  add_step "Delete WordPress files" "step_delete_wp_files" "undo_delete_wp_files"
  add_step "Drop database & user" "step_drop_db" "undo_drop_db" "If a backup path was provided, undo will attempt a restore."

  run_stages "Uninstall Stages"
  print_green "Done. Uninstall mode '${MODE}' completed."
}

# ================================
# INSTALL workflow (menu wrapper)
# ================================
install_menu(){
  check_ports_80_443
  echo
  local user_choice
  read -r -p "Do you want to continue with the script execution? (yes/no): " user_choice
  user_choice="${user_choice,,}"
  if [[ ! "$user_choice" =~ ^(yes|y)$ ]]; then
    print_red "❌ Script execution aborted by the user."
    exit 0
  fi

  local server_ip db_name db_user db_password wp_password
  read -r -p "Enter your server IP address: " server_ip
  read -r -p "Enter your database name: " db_name
  read -r -p "Enter your database username: " db_user
  read -r -s -p "Enter your database password: " db_password; echo
  read -r -s -p "Enter the WordPress database password (same as above unless different): " wp_password; echo
  [ -z "$wp_password" ] && wp_password="$db_password"

  local APACHE_ROOT="$APACHE_ROOT_DEFAULT"
  local WP_DIR="$WP_DIR_DEFAULT"

  reset_steps
  add_step "Install prerequisites" "install_prereqs" "undo_install_prereqs"
  add_step "Install PHP" "install_php" "undo_install_php"
  add_step "Install MySQL server" "install_mysql" "undo_install_mysql"
  install_create_db_user(){ configure_mysql_wp "$db_name" "$db_user" "$db_password"; }
  install_undo_create_db_user(){ undo_configure_mysql_wp "$db_name" "$db_user"; }
  add_step "Create DB & user" "install_create_db_user" "install_undo_create_db_user"
  add_step "Install Apache" "install_apache" "undo_install_apache"
  dl_wp(){ download_wordpress "$APACHE_ROOT" "$WP_DIR"; }
  undo_dl_wp(){ undo_download_wordpress "$WP_DIR"; }
  add_step "Download WordPress" "dl_wp" "undo_dl_wp"
  cfg_wp(){ configure_wp_config "$WP_DIR" "$db_name" "$db_user" "$db_password"; }
  undo_cfg_wp(){ undo_configure_wp_config "$WP_DIR"; }
  add_step "Configure wp-config.php" "cfg_wp" "undo_cfg_wp"
  add_step "Restart Apache" "restart_apache" "restart_apache"

  run_stages "Installation Stages"

  print_green "✅ WordPress installation is complete."
  echo "🌐 Visit: http://${server_ip}/wordpress"
  echo "📌 If using a domain, ensure your DNS points to ${server_ip}"
  echo "🛠️ Finish setup in the browser interface."
}

# ================================
# HARDEN workflow (menu wrapper)
# ================================
harden_menu(){
  local wp_dir wp_cfg_path
  read -r -p "WordPress directory? [${WP_DIR_DEFAULT}]: " wp_dir
  wp_dir="${wp_dir:-$WP_DIR_DEFAULT}"
  read -r -p "Secure path to move wp-config.php? [${WP_CONFIG_NEW_PATH_DEFAULT}]: " wp_cfg_path
  wp_cfg_path="${wp_cfg_path:-$WP_CONFIG_NEW_PATH_DEFAULT}"
  harden_wordpress "$APACHE_ROOT_DEFAULT" "$wp_dir" "$wp_cfg_path"
  print_green "🗒️ A security report was saved to /var/log/wp_security_report.txt"
}

# ================================
# MAIN MENU
# ================================
preflight_dummy(){ :; } # visual consistency
main_menu(){
  echo
  printf "%bWordPress Manager — choose an action:%b\n" "$BOLD" "$RESET"
  echo " 1) Install WordPress (LAMP + WP)"
  echo " 2) Harden existing WordPress (built-in)"
  echo " 3) Uninstall / Purge WordPress (interactive modes)"
  echo " 4) Exit"
  echo
  local sel
  read -r -p "Enter 1/2/3/4: " sel
  case "$sel" in
    1)
      reset_steps; add_step "Root & logging setup" "preflight_dummy" "" ; run_stages "Preflight"
      install_menu
      ;;
    2)
      reset_steps; add_step "Root & logging setup" "preflight_dummy" "" ; run_stages "Preflight"
      harden_menu
      ;;
    3)
      reset_steps; add_step "Root & logging setup" "preflight_dummy" "" ; run_stages "Preflight"
      uninstall_menu
      ;;
    4) echo "Bye."; exit 0 ;;
    *) error "Invalid selection."; exit 2 ;;
  esac
}

# ================================
# Entry
# ================================
main(){
  require_root
  setup_logging
  main_menu
}
main "$@"
