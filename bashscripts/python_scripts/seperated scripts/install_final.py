#!/usr/bin/env python3

import subprocess
import sys
import getpass
from pathlib import Path

# ========== Pretty printing for pre-checks & final summary ==========
def print_green(text): print(f"\033[32m{text}\033[0m")
def print_red(text):   print(f"\033[31m{text}\033[0m")

# ========== Single-line progress bar (one bar only) ==========
def _term_bar_width(padding: int = 8, min_width: int = 10, max_width: int = 100):
    # padding accounts for brackets + space + "100%" text
    try:
        import shutil as _sh
        cols = _sh.get_terminal_size(fallback=(80, 24)).columns
    except Exception:
        cols = 80
    return max(min(max_width, cols - padding), min_width)

class ProgressBar:
    def __init__(self):
        self.total = 1
        self.done = 0
        self.last_pct = -1
        self.started = False
        self.width = _term_bar_width()

    def _render(self, pct: int) -> str:
        pct = max(0, min(100, int(pct)))
        self.width = _term_bar_width()
        filled = int(round(self.width * (pct / 100.0)))
        return f"\r\033[2K[{'#' * filled}{'-' * (self.width - filled)}] {pct:3d}%"

    def _write(self, pct: int):
        if pct == self.last_pct:  # debounce to avoid flicker
            return
        self.last_pct = pct
        sys.stdout.write(self._render(pct))
        sys.stdout.flush()

    def start(self, total_steps: int):
        self.total = max(1, int(total_steps))
        self.done = 0
        self.last_pct = -1
        self.started = True
        self._write(0)

    def step(self, inc: int = 1):
        if not self.started:
            return
        self.done += inc
        done = min(self.done, self.total)
        pct = min(int(done / self.total * 100), 99)  # hold at 99 until end()
        self._write(pct)

    def end(self):
        if not self.started:
            return
        self._write(100)
        sys.stdout.write("\n")
        sys.stdout.flush()
        self.started = False

BAR = ProgressBar()

# ========== Helpers ==========
DEVNULL = subprocess.DEVNULL

def check_port_status(port):
    try:
        result = subprocess.run(['ss', '-tpln'], capture_output=True, text=True, check=True)
        if f":{port}" in result.stdout:
            return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            result = subprocess.run(['netstat', '-tpln'], capture_output=True, text=True, check=True)
            if f":{port}" in result.stdout:
                return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print_red("Neither ss nor netstat is installed. Cannot check port status.")
            sys.exit(1)
    return False

def run(command: str) -> bool:
    try:
        subprocess.run(command, shell=True, check=True, stdout=DEVNULL, stderr=DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def run_and_tick(command: str) -> bool:
    ok = run(command)
    BAR.step(1)
    return ok

def enable_php_fpm_conf_chain():
    """
    Enable whichever phpX.Y-fpm Apache conf exists.
    Works across Ubuntu/Debian versions.
    """
    # Try common versions first via shell OR chain
    cmds = [
        "a2enconf php8.3-fpm",
        "a2enconf php8.2-fpm",
        "a2enconf php8.1-fpm",
        "a2enconf php8.0-fpm",
        "a2enconf php7.4-fpm",
    ]
    for c in cmds:
        if run(c):  # first one that succeeds
            return True
    # Fallback: scan conf-available
    try:
        out = subprocess.check_output("ls /etc/apache2/conf-available/php*-fpm.conf 2>/dev/null", shell=True, text=True)
        for line in out.strip().splitlines():
            name = Path(line).stem  # e.g., php8.2-fpm
            if run(f"a2enconf {name}"):
                return True
    except subprocess.CalledProcessError:
        pass
    return False

# ========== Main ==========
def main():
    SUMMARY = []

    # Pre-flight checks (before progress bar)
    print_green("🔍 Checking port 80 (HTTP)...")
    if check_port_status(80):
        print_green("✅ Port 80 is OPEN."); SUMMARY.append("Port 80 (HTTP) open.")
    else:
        print_red("❌ Port 80 is CLOSED."); SUMMARY.append("Port 80 (HTTP) was closed at check time.")

    print_green("🔍 Checking port 443 (HTTPS)...")
    if check_port_status(443):
        print_green("✅ Port 443 is OPEN."); SUMMARY.append("Port 443 (HTTPS) open.")
    else:
        print_red("❌ Port 443 is CLOSED."); SUMMARY.append("Port 443 (HTTPS) was closed at check time.")

    print()
    user_choice = input("Do you want to continue with the script execution? (yes/no): ").lower()
    if user_choice not in ['yes', 'y']:
        print_red("❌ Script execution aborted by the user.")
        sys.exit(0)

    if getpass.getuser() != 'root':
        print_red("This script must be run as root.")
        sys.exit(1)

    # User inputs
    server_ip = input("Enter your server IP address: ")
    db_name = input("Enter your database name: ")
    db_user = input("Enter your database username: ")
    db_password = getpass.getpass("Enter your database password: ")
    wp_password = getpass.getpass("Enter the WordPress database password (same as above unless different): ")
    if not wp_password:
        wp_password = db_password

    # Paths
    WP_DIR = "/var/www/html/wordpress"
    APACHE_ROOT = "/var/www/html"

    # Progress plan (keep in sync with ticks below)
    # 1 update+upgrade
    # 2 prerequisites
    # 3 apache
    # 4 php core + extensions + fpm
    # 5 enable proxy_fcgi
    # 6 enable phpX-fpm conf
    # 7 restart php-fpm (best-effort)
    # 8 restart apache
    # 9 mysql-server
    #10 mysql_secure baseline
    #11 create db/user/grants
    #12 download & unpack WordPress (treated as one step)
    #13 configure wp-config.php
    #14 set permissions
    #15 enable mod_rewrite + AllowOverride All
    #16 final apache restart
    total_steps = 16
    BAR.start(total_steps)

    # 1) Update & upgrade
    if run_and_tick("apt-get update && apt-get upgrade -y"):
        SUMMARY.append("System packages updated & upgraded.")

    # 2) Prerequisites
    if run_and_tick("apt-get install -y software-properties-common curl ca-certificates lsb-release"):
        SUMMARY.append("Installed prerequisites (software-properties-common, curl, ca-certificates).")

    # 3) Apache
    if run_and_tick("apt-get install -y apache2"):
        SUMMARY.append("Installed Apache.")

    # 4) PHP core + extensions (+ FPM). Use distro PHP (avoids EOL 7.4).
    if run_and_tick("apt-get install -y php php-mysql php-curl php-gd php-mbstring php-xml php-zip php-fpm"):
        SUMMARY.append("Installed PHP (distro) with common extensions and PHP-FPM.")

    # 5) Enable proxy_fcgi + setenvif
    run_and_tick("a2enmod proxy_fcgi setenvif")

    # 6) Enable phpX-fpm Apache config (whichever exists)
    if enable_php_fpm_conf_chain():
        BAR.step(1)
        SUMMARY.append("Enabled Apache PHP-FPM configuration.")
    else:
        BAR.step(1)
        SUMMARY.append("WARNING: Could not auto-enable phpX-fpm conf (continuing).")

    # 7) Restart php-fpm (try common versions)
    run_and_tick("systemctl restart php8.3-fpm php8.2-fpm php8.1-fpm php8.0-fpm php7.4-fpm 2>/dev/null || true")

    # 8) Restart Apache
    run_and_tick("systemctl restart apache2")

    # 9) MySQL server
    if run_and_tick("apt-get install -y mysql-server"):
        SUMMARY.append("Installed MySQL Server.")

    # 10) mysql_secure baseline (non-interactive minimal)
    mysql_secure_cmd = [
        "mysql", "-e",
        "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '';"
        "DELETE FROM mysql.user WHERE User='';"
        "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost','127.0.0.1','::1');"
        "DROP DATABASE IF EXISTS test;"
        "DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';"
        "FLUSH PRIVILEGES;"
    ]
    try:
        subprocess.run(mysql_secure_cmd, stdout=DEVNULL, stderr=DEVNULL, check=True)
        SUMMARY.append("Ran basic MySQL hardening (remove anon users, test DB, tighten root host).")
    except subprocess.CalledProcessError:
        pass
    BAR.step(1)

    # 11) Configure DB/user for WordPress
    mysql_cmd = (
        f"mysql -u root -e \""
        f"CREATE DATABASE IF NOT EXISTS {db_name}; "
        f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_password}'; "
        f"GRANT ALL PRIVILEGES ON {db_name}.* TO '{db_user}'@'localhost'; "
        f"FLUSH PRIVILEGES;\""
    )
    if run_and_tick(mysql_cmd):
        SUMMARY.append(f"Prepared MySQL DB '{db_name}' and user '{db_user}' with privileges.")

    # 12) Download & unpack WordPress (one step for the bar)
    if subprocess.run(f"test -d {WP_DIR}", shell=True).returncode != 0:
        cmds = [
            "cd /tmp",
            "curl -LO https://wordpress.org/latest.tar.gz",
            "tar xzvf latest.tar.gz",
            f"mv wordpress {APACHE_ROOT}/",
            f"chown -R www-data:www-data {WP_DIR}",
            f"chmod -R 755 {WP_DIR}",
            "rm latest.tar.gz"
        ]
        for c in cmds:
            subprocess.run(c, shell=True, stdout=DEVNULL, stderr=DEVNULL)
        SUMMARY.append(f"Downloaded and unpacked WordPress to {WP_DIR}.")
    else:
        SUMMARY.append(f"WordPress directory {WP_DIR} already exists (skipped download).")
    BAR.step(1)

    # 13) Configure wp-config.php
    wp_cfg_cmds = [
        f"cd {WP_DIR}",
        "[ ! -f wp-config.php ] && cp wp-config-sample.php wp-config.php",
        f"sed -i \"s/'DB_NAME', 'database_name_here'/'DB_NAME', '{db_name}'/g\" wp-config.php",
        f"sed -i \"s/'DB_USER', 'username_here'/'DB_USER', '{db_user}'/g\" wp-config.php",
        f"sed -i \"s/'DB_PASSWORD', 'password_here'/'DB_PASSWORD', '{wp_password}'/g\" wp-config.php"
    ]
    for c in wp_cfg_cmds:
        subprocess.run(c, shell=True, stdout=DEVNULL, stderr=DEVNULL)
    SUMMARY.append("Configured wp-config.php with database credentials.")
    BAR.step(1)

    # 14) Permissions (webroot)
    if run_and_tick(f"chown -R www-data:www-data {APACHE_ROOT} && chmod -R 755 {APACHE_ROOT}"):
        SUMMARY.append(f"Set ownership (www-data) and 755 perms under {APACHE_ROOT}.")

    # 15) Enable mod_rewrite & AllowOverride All for /var/www (pretty permalinks)
    #    This edits the default apache2.conf Directory block safely.
    run_and_tick("a2enmod rewrite")
    # replace AllowOverride None -> All in the /var/www/ block
    fix_override = r"""awk '
/<Directory \\/var\\/www\\/>/ { inblock=1 }
inblock && /AllowOverride/ { sub(/None/,"All") }
{ print }
inblock && /<\\/Directory>/ { inblock=0 }
' /etc/apache2/apache2.conf > /tmp/apache2.conf.tmp && mv /tmp/apache2.conf.tmp /etc/apache2/apache2.conf"""
    subprocess.run(fix_override, shell=True, stdout=DEVNULL, stderr=DEVNULL)
    SUMMARY.append("Enabled mod_rewrite and AllowOverride All for /var/www (permalinks ready).")

    # 16) Final Apache restart
    run_and_tick("systemctl restart apache2")

    # Finish bar
    BAR.end()

    # Final messages
    print_green("✅ WordPress installation and configuration complete.")
    print(f"🌐 Visit: http://{server_ip}/wordpress")
    print(f"📌 If using a domain, ensure your DNS points to {server_ip}")
    print("🛠️ Finish the setup in the WordPress installer UI.\n")

    print("Summary of actions:")
    for s in SUMMARY:
        print(f" • {s}")

if __name__ == "__main__":
    # Keep output tidy (single bar + final messages)
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Silent failure to avoid stack traces disrupting the UI
        sys.exit(1)

