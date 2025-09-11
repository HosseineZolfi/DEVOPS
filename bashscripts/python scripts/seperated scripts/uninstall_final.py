#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# wp-uninstall.py — Interactive WordPress uninstaller (files/db/apps) with ONE progress bar
#
# Modes:
#   1) content-only : remove WP files and DB/user (keep Apache/MySQL/PHP)
#   2) complete     : remove apps + configs + WP files + DB/user
#   3) apps-only    : remove Apache/MySQL/PHP (keep files + DB)
#
# Notes:
# - Progress bar: single line, adaptive width, filled with '#' per percent.
# - Commands run silently so the bar stays clean.
# - “Undo” prompts removed to keep the one-bar UX consistent.

import getpass
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ================================
# Pretty printing for prompts/final output
# ================================
def print_green(msg: str): print(f"\033[32m{msg}\033[0m")
def print_yellow(msg: str): print(f"\033[33m{msg}\033[0m")
def print_red(msg: str): print(f"\033[31m{msg}\033[0m")

def require_root():
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print_red("This script must be run as root.")
        sys.exit(1)

def confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() in ("y", "yes")

def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None

# ================================
# Single-line progress bar (one bar only)
# ================================
def _term_bar_width(padding: int = 8, min_width: int = 10, max_width: int = 100):
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
        if pct == self.last_pct:
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
DEVNULL = subprocess.DEVNULL

def run_silent(cmd: str, tick: bool = True) -> bool:
    try:
        subprocess.run(cmd, shell=True, check=True, stdout=DEVNULL, stderr=DEVNULL)
        if tick: BAR.step(1)
        return True
    except subprocess.CalledProcessError:
        if tick: BAR.step(1)  # still advance so the bar doesn't hang
        return False

# ================================
# Detect package manager & services
# ================================
PKG = None
APACHE_SVC = None
SQL_SVC = None

def detect_pm_services():
    global PKG, APACHE_SVC, SQL_SVC
    if command_exists("apt-get"):
        PKG = "apt"
    elif command_exists("dnf"):
        PKG = "dnf"
    elif command_exists("yum"):
        PKG = "yum"
    else:
        print_red("Unsupported system: no apt, dnf, or yum found.")
        sys.exit(1)

    def has_unit(name: str) -> bool:
        return subprocess.run(f"systemctl list-unit-files | grep -q '^{name}\\.service'", shell=True).returncode == 0

    if has_unit("apache2"):
        APACHE_SVC = "apache2"
    elif has_unit("httpd"):
        APACHE_SVC = "httpd"

    if has_unit("mysql"):
        SQL_SVC = "mysql"
    elif has_unit("mariadb"):
        SQL_SVC = "mariadb"

# ================================
# MySQL helpers (silent)
# ================================
def mysql_exec_embedded(sql: str, root_pw: str):
    if not root_pw:
        run_silent(f"mysql -u root --protocol=socket --batch --raw --execute \"{sql}\"")
    else:
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(f"[client]\nuser=root\npassword={root_pw}\nprotocol=socket\n"); tf.flush()
            run_silent(f"mysql --defaults-extra-file={tf.name} --batch --raw --execute \"{sql}\"")
        os.unlink(tf.name)

def mysqldump_embedded(db: str, outpath: str, root_pw: str):
    if not root_pw:
        run_silent(f"mysqldump -u root --single-transaction --routines --triggers {db} > {outpath}")
    else:
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(f"[client]\nuser=root\npassword={root_pw}\nprotocol=socket\n"); tf.flush()
            run_silent(f"mysqldump --defaults-extra-file={tf.name} --single-transaction --routines --triggers {db} > {outpath} || true")
        os.unlink(tf.name)

# ================================
# Uninstall flow
# ================================
def uninstall_menu():
    detect_pm_services()

    # Auto-detect WP dir
    wp_dir = None
    for cand in ["/var/www/html/wordpress", "/var/www/wordpress", "/srv/www/wordpress", "/var/www/html"]:
        pc = Path(cand)
        if (pc.is_dir() and (pc / "wp-admin").exists()) or (pc / "wp-config.php").exists():
            wp_dir = pc
            break
    if not wp_dir:
        wp_dir = Path("/var/www/html/wordpress")

    print_green("Choose uninstall mode:")
    print(" 1) Remove WordPress content only (files + DB/user; keep apps)")
    print(" 2) Complete delete (apps + configs + WP files + DB/user)")
    print(" 3) Remove apps only (keep WP files + DB/user)")
    choice = input("Enter 1/2/3: ").strip()

    if choice == "1":
        MODE = "content-only"
    elif choice == "2":
        MODE = "complete"
    elif choice == "3":
        MODE = "apps-only"
    else:
        print_red("Invalid selection."); sys.exit(2)

    needs_db = needs_files = remove_packages = purge_packages = False
    if MODE == "content-only":
        needs_db = needs_files = True
    elif MODE == "complete":
        needs_db = needs_files = True
        remove_packages = True
        purge_packages = True
    elif MODE == "apps-only":
        remove_packages = True

    DB_NAME = DB_USER = MYSQL_ROOT_PASSWORD = BACKUP_SQL = ""
    if needs_db:
        DB_NAME = input("Enter the database name to delete: ").strip()
        DB_USER = input("Enter the database user to delete: ").strip()
        MYSQL_ROOT_PASSWORD = getpass.getpass("Enter the MySQL root password (leave empty for socket auth): ")
        BACKUP_SQL = input("Optional: path to backup SQL before delete (leave empty to skip): ").strip()
        if DB_NAME in ("mysql", "sys", "performance_schema", "information_schema"):
            print_red(f"Refusing to drop critical database '{DB_NAME}'."); sys.exit(3)
        if DB_USER == "root":
            print_red("Refusing to drop user 'root'."); sys.exit(3)

    print_yellow("\nPlan:")
    if MODE == "content-only":
        print(f" - Delete WordPress files under '{wp_dir}'")
        print(f" - Drop DB '{DB_NAME}' and user '{DB_USER}'@'localhost'")
        print(" - Keep Apache/MySQL/PHP installed")
    elif MODE == "complete":
        print(" - Remove Apache/MySQL/PHP (purge configs/data)")
        print(f" - Delete WordPress files under '{wp_dir}'")
        print(f" - Drop DB '{DB_NAME}' and user '{DB_USER}'@'localhost'")
    elif MODE == "apps-only":
        print(" - Remove Apache/MySQL/PHP packages (keep files + DB)")
    print()

    if not confirm("Proceed into staged uninstall now?"):
        print_yellow("Aborted.")
        return

    trash = Path("/var/tmp/wp-manager-trash") / str(int(time.time()))
    trash.mkdir(parents=True, exist_ok=True)

    # ===== Progress plan =====
    # We'll estimate steps to keep the bar smooth. Adjust if you add/remove commands.
    # Stop services: up to 2
    # Remove packages: ~10
    # Delete files: ~5
    # Drop DB: ~3
    total_steps = 2 + (10 if remove_packages else 0) + (5 if MODE != "apps-only" else 0) + (3 if needs_db else 0)
    if total_steps == 0:
        total_steps = 1
    BAR.start(total_steps)

    # ---- Stage 1: Stop services ----
    if APACHE_SVC:
        run_silent(f"systemctl stop {APACHE_SVC} || true")
    else:
        BAR.step(1)
    if SQL_SVC and remove_packages:
        run_silent(f"systemctl stop {SQL_SVC} || true")
    elif remove_packages:
        BAR.step(1)

    # ---- Stage 2: Remove packages (optional) ----
    if remove_packages:
        if PKG == "apt":
            if purge_packages:
                run_silent("apt-get remove --purge -y apache2 apache2-utils apache2-bin || true")
                run_silent("apt-get remove --purge -y mysql-server mysql-client mariadb-server mariadb-client mysql-common mariadb-common || true")
                run_silent("apt-get remove --purge -y 'php*' 'libapache2-mod-php*' || true")
            else:
                run_silent("apt-get remove -y apache2 apache2-utils apache2-bin || true")
                run_silent("apt-get remove -y mysql-server mysql-client mariadb-server mariadb-client || true")
                run_silent("apt-get remove -y 'php*' 'libapache2-mod-php*' || true")
            run_silent("apt-get -y autoremove || true")
            run_silent("apt-get -y autoclean || true")
            if purge_packages:
                run_silent("rm -rf /etc/mysql /var/lib/mysql /var/lib/mariadb || true")
            if command_exists("add-apt-repository"):
                # best-effort PPA removal
                subprocess.run("grep -qi 'ppa.launchpadcontent.net/ondrej/php' /etc/apt/sources.list.d/*.list 2>/dev/null",
                               shell=True, stdout=DEVNULL, stderr=DEVNULL)
                run_silent("add-apt-repository --remove -y ppa:ondrej/php || true")
        else:  # dnf / yum
            PMBIN = f"{PKG} -y"
            run_silent(f"{PMBIN} remove httpd httpd-tools || true")
            run_silent(f"{PMBIN} remove mysql-server mariadb-server mariadb || true")
            run_silent(f"{PMBIN} remove 'php*' php-cli php-fpm mod_php || true")
            if PKG == "dnf":
                run_silent("dnf autoremove -y || true")
                run_silent("dnf clean all || true")
            else:
                run_silent("yum autoremove -y || true")
                run_silent("yum clean all || true")
            if purge_packages:
                run_silent("rm -rf /etc/my.cnf /etc/mysql /var/lib/mysql /var/lib/mariadb || true")

    # ---- Stage 3: Delete WordPress files (optional) ----
    if MODE != "apps-only":
        # Move WP dir to trash
        if wp_dir.exists():
            dst = trash / "wordpress-files"
            try:
                shutil.move(str(wp_dir), str(dst))
            except Exception:
                pass
            BAR.step(1)
        else:
            BAR.step(1)

        # Move common wp-config* files if present
        for f in ["/var/www/html/wp-config.php", "/var/www/html/wp-config-sample.php"]:
            p = Path(f)
            if p.exists():
                try:
                    shutil.move(str(p), str(trash / p.name))
                except Exception:
                    pass
            BAR.step(1)

        # Reset /var/www/html perms (best-effort)
        if Path("/var/www/html").exists():
            run_silent("chown -R root:root /var/www/html")
            run_silent("find /var/www/html -type d -exec chmod 755 {} +")
            run_silent("find /var/www/html -type f -exec chmod 644 {} +")
        else:
            BAR.step(3)  # consume equivalent ticks if folder missing

    # ---- Stage 4: Drop DB & user (optional) ----
    if needs_db:
        if BACKUP_SQL:
            # Best-effort backup before delete
            mysqldump_embedded(DB_NAME, BACKUP_SQL, MYSQL_ROOT_PASSWORD)
        # Drop DB & user
        mysql_exec_embedded(f"""
            SET sql_notes=0;
            DROP DATABASE IF EXISTS {DB_NAME};
            DROP USER IF EXISTS '{DB_USER}'@'localhost';
            FLUSH PRIVILEGES;
        """, MYSQL_ROOT_PASSWORD)
        BAR.step(1)  # already ticked within helpers, ensure total aligns

    # Finish bar
    BAR.end()

    # Final message
    print_green(f"✅ Uninstall mode '{MODE}' completed.")
    if MODE != "apps-only":
        print_green(f"🗑️  Files moved (if found) to: {trash}")

# ================================
# Entry
# ================================
def main():
    require_root()
    uninstall_menu()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Keep output tidy (no stack traces breaking the bar)
        sys.exit(1)

