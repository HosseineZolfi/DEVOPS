#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# wp-manager.py — Install / Harden / Uninstall (Purge) WordPress via interactive, staged menu
# Now with: live per-stage progress bars (auto-updating), optional undo, and no per-stage pre-confirmation
#
# - INSTALL: LAMP + WordPress (subdir /var/www/html/wordpress) with port checks & prompts
# - HARDEN : Built-in hardening (no external modules; no Let's Encrypt)
# - UNINSTALL (PURGE): content-only | complete | apps-only — staged with best-effort undo
#
# DISCLAIMER: "Undo" is best-effort. Package operations and firewall rules can be hard to
# perfectly revert across distros or previously-customized hosts. This tool attempts safe,
# minimal, *documented* reversions for exactly-just-applied changes. Always review prompts
# and keep backups for production systems.

import atexit
import datetime as dt
import getpass
import os
import pwd
import grp
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional, List

# ================================
# Colors & UI helpers
# ================================
USE_TTY = sys.stdout.isatty()

def _ansi(code: str) -> str:
    return f"\033[{code}m" if USE_TTY else ""

GREEN = _ansi("32")
RED = _ansi("31")
YELLOW = _ansi("33")
CYAN = _ansi("36")
BOLD = _ansi("1")
RESET = _ansi("0")


def print_green(msg: str):
    print(f"{GREEN}{msg}{RESET}")


def print_red(msg: str):
    print(f"{RED}{msg}{RESET}")


def print_yellow(msg: str):
    print(f"{YELLOW}{msg}{RESET}")


def print_cyan(msg: str):
    print(f"{CYAN}{msg}{RESET}")


def log(msg: str):
    print(f"{GREEN}[*]{RESET} {msg}")


def warn(msg: str):
    print(f"{YELLOW}[!]{RESET} {msg}", file=sys.stderr)


def error(msg: str):
    print(f"{RED}[x]{RESET} {msg}", file=sys.stderr)


# ================================
# Root check & logging
# ================================

def require_root():
    if hasattr(os, "geteuid"):
        if os.geteuid() != 0:
            error("This script must be run as root.")
            sys.exit(1)


LOG_FILE = Path("/var/log/wp_manager.log")


def setup_logging():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # tee-like: duplicate stdout/stderr to file
    class Tee(object):
        def __init__(self, *streams):
            self.streams = streams

        def write(self, data):
            for s in self.streams:
                s.write(data)

        def flush(self):
            for s in self.streams:
                s.flush()

    # open append text, unbuffered-ish
    f = open(LOG_FILE, "a", buffering=1)
    sys.stdout = Tee(sys.__stdout__, f)
    sys.stderr = Tee(sys.__stderr__, f)
    print(f"\n===== {dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')} :: wp-manager start =====")


def cleanup():
    code = 0
    print(f"===== {dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')} :: wp-manager end (exit {code}) =====")


atexit.register(cleanup)

# global error trap

def _excepthook(exc_type, exc, tb):
    error(f"Failed: {exc_type.__name__}: {exc}")
    sys.exit(1)


sys.excepthook = _excepthook


# ================================
# Generic helpers
# ================================

def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def confirm(prompt: str) -> bool:
    ans = input(f"{prompt} [y/N]: ").strip().lower()
    return ans in ("y", "yes")


# ========== Progress tracking (NEW) ==========
_CURRENT_PROGRESS = {"active": False, "label": "", "done": 0, "total": 1}

def _bar(pct: int, width: int = 36) -> str:
    pct = max(0, min(100, int(pct)))
    filled = int(width * (pct / 100.0))
    return f"[{'#' * filled}{'-' * (width - filled)}] {pct:3d}%"

def show_bar(label: str, pct: int):
    line = f"{CYAN}{label:<28}{RESET} {_bar(pct)}"
    if USE_TTY:
        print("\r" + line, end="", flush=True)
    else:
        print(line)

def end_bar():
    if USE_TTY:
        print()

def _progress_start(label: str, total_ops: int):
    _CURRENT_PROGRESS.update(active=True, label=label, done=0, total=max(1, int(total_ops)))
    show_bar(label, 0)

def progress_tick(inc: int = 1):
    if not _CURRENT_PROGRESS["active"]:
        return
    _CURRENT_PROGRESS["done"] += inc
    # Cap at 99% during the step; final 100% is set by _progress_end()
    done = min(_CURRENT_PROGRESS["done"], _CURRENT_PROGRESS["total"])
    pct = int(done / _CURRENT_PROGRESS["total"] * 100)
    pct = min(pct, 99)
    show_bar(_CURRENT_PROGRESS["label"], pct)

def _progress_end():
    if not _CURRENT_PROGRESS["active"]:
        return
    show_bar(_CURRENT_PROGRESS["label"], 100)
    end_bar()
    _CURRENT_PROGRESS["active"] = False


def run(cmd, check=True, shell=True, env=None):
    """Run a command (string or list). Mirrors bash run. Ticks progress after each command."""
    if isinstance(cmd, list):
        cmd_str = " ".join(cmd)
    else:
        cmd_str = cmd
    log(f"$ {cmd_str}")
    r = subprocess.run(
        cmd,
        shell=shell,
        executable="/bin/bash" if shell else None,
        check=check,
        env=env,
    )
    # progress bar tick for each external command that finishes
    progress_tick(1)
    return r


# ================================
# Progress-bar & Stage framework
# ================================

@dataclass
class Step:
    name: str
    do: Callable[[], None]
    undo: Optional[Callable[[], None]] = None
    note: str = ""
    expected_ops: int = 1  # NEW: approximate number of sub-ops for live progress


class StageRunner:
    def __init__(self, title: str, steps: List[Step]):
        self.title = title
        self.steps = steps
        self.total = len(steps)

    def run(self):
        print()
        print(f"{BOLD}{self.title}{RESET}")
        completed = 0
        for idx, step in enumerate(self.steps, 1):
            print()
            print_cyan(f"— Stage {idx}/{self.total}: {step.name}")
            if step.note:
                print_yellow(f"  {step.note}")

            # (CHANGED) No "Proceed with this stage?" prompt — run immediately
            start = time.time()
            _progress_start(step.name, step.expected_ops)
            try:
                step.do()
                _progress_end()
            except subprocess.CalledProcessError as e:
                _progress_end()
                error(f"Command failed during stage '{step.name}': {e}")
                if step.undo and confirm("Attempt to undo this stage now?"):
                    try:
                        step.undo()
                        print_yellow("Reverted (best-effort).")
                    except Exception as ue:
                        error(f"Undo failed: {ue}")
                sys.exit(1)

            elapsed = int(time.time() - start)
            log(f"Stage completed in ~{elapsed}s")

            # Post-stage choice (unchanged)
            while True:
                ans = input("Next action — [C]ontinue, [U]ndo this stage, [A]bort: ").strip().lower()
                if ans in ("", "c", "cont", "continue", "y", "yes"):
                    break
                if ans in ("u", "undo"):
                    if step.undo:
                        try:
                            print_yellow("Undoing this stage…")
                            step.undo()
                            print_green("Stage undone (best-effort).")
                        except Exception as ue:
                            error(f"Undo failed: {ue}")
                    else:
                        warn("No automatic undo is available for this stage.")
                    if confirm("Proceed to the next stage?"):
                        break
                    else:
                        warn("Aborted by user after undo.")
                        sys.exit(0)
                if ans in ("a", "abort", "q", "quit"):
                    warn("Aborted by user.")
                    sys.exit(0)
            completed += 1
        print_green("✅ All selected stages completed.")


# ================================
# Port check helpers
# ================================

def check_port_status(port):
    try:
        # Try using ss first
        result = subprocess.run(['ss', '-tpln'], capture_output=True, text=True, check=True)
        if f":{port}" in result.stdout:
            return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            # Fall back to netstat if ss fails
            result = subprocess.run(['netstat', '-tpln'], capture_output=True, text=True, check=True)
            if f":{port}" in result.stdout:
                return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print_red("Neither ss nor netstat is installed. Cannot check port status.")
            sys.exit(1)
    return False

def run_command(command, description, progress_callback=None):
    """Run a command and optionally update progress"""
    if progress_callback:
        progress_callback()
    
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def check_ports_80_443():
    # Check ports first
    print_green("🔍 Checking port 80 (HTTP)...")
    if check_port_status(80):
        print_green("✅ Port 80 is OPEN.")
    else:
        print_red("❌ Port 80 is CLOSED.")

    print_green("🔍 Checking port 443 (HTTPS)...")
    if check_port_status(443):
        print_green("✅ Port 443 is OPEN.")
    else:
        print_red("❌ Port 443 is CLOSED.")

# ================================
# Paths / config
# ================================
APACHE_ROOT_DEFAULT = Path("/var/www/html")
WP_DIR_DEFAULT = APACHE_ROOT_DEFAULT / "wordpress"
WP_CONFIG_NEW_PATH_DEFAULT = Path("/var/www")
STATE_DIR = Path("/var/lib/wp-manager")
STATE_DIR.mkdir(parents=True, exist_ok=True)
TRASH_ROOT = Path("/var/tmp/wp-manager-trash")
TRASH_ROOT.mkdir(parents=True, exist_ok=True)

# In-memory session state for this run
RUN_STATE = {"backups": []}

def _backup(path: Path):
    """Backup a file and record it for potential undo"""
    if not path.exists():
        return
    bak = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
    shutil.copy2(path, bak)
    RUN_STATE["backups"].append((str(path), str(bak)))
    return bak

# ================================
# HARDEN — Embedded functions
# ================================

def configure_firewall():
    print_green("🧱 Configuring firewall…")
    if not command_exists("ufw"):
        run("apt-get update -y && apt-get install -y ufw || true")
    if command_exists("ufw"):
        snap = STATE_DIR / "ufw.status.before"
        try:
            with open(snap, "w") as f:
                subprocess.run("ufw status verbose", shell=True, check=False, stdout=f, stderr=subprocess.STDOUT)
        except Exception:
            pass
        run("ufw --force reset >/dev/null 2>&1 || true")
        run("ufw default deny incoming")
        run("ufw default allow outgoing")
        run("ufw allow OpenSSH || ufw allow 22 || true")
        if subprocess.run("ufw app list 2>/dev/null | grep -q 'Apache Full'", shell=True).returncode == 0:
            run('ufw allow "Apache Full"')
        else:
            run("ufw allow 80/tcp")
            run("ufw allow 443/tcp")
        run("yes | ufw enable >/dev/null 2>&1 || ufw enable || true")
        run("ufw status verbose || true")
    elif command_exists("firewall-cmd"):
        run("systemctl enable --now firewalld || true")
        run("firewall-cmd --permanent --add-service=http || firewall-cmd --permanent --add-port=80/tcp")
        run("firewall-cmd --permanent --add-service=https || firewall-cmd --permanent --add-port=443/tcp")
        run("firewall-cmd --permanent --add-service=ssh || firewall-cmd --permanent --add-port=22/tcp")
        run("firewall-cmd --reload || true")
        run("firewall-cmd --list-all || true")
    else:
        warn("No ufw/firewalld found; applying basic iptables (volatile) rules…")
        run("iptables -P INPUT DROP || true")
        run("iptables -P FORWARD DROP || true")
        run("iptables -P OUTPUT ACCEPT || true")
        run("iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT || true")
        run("iptables -A INPUT -p tcp --dport 22 -j ACCEPT || true")
        run("iptables -A INPUT -p tcp --dport 80 -j ACCEPT || true")
        run("iptables -A INPUT -p tcp --dport 443 -j ACCEPT || true")
        run("iptables -A INPUT -i lo -j ACCEPT || true")

def undo_configure_firewall():
    if command_exists("ufw"):
        print_yellow("Disabling ufw and restoring prior state snapshot if any…")
        run("ufw --force disable || true")
        snap = STATE_DIR / "ufw.status.before"
        if snap.exists():
            warn("Automatic re-apply from snapshot is not supported; please reconfigure manually if needed.")
    elif command_exists("firewall-cmd"):
        print_yellow("Reloading firewalld defaults (best-effort)…")
        run("firewall-cmd --reload || true")
    else:
        warn("No firewall tool available to undo.")

def setup_fail2ban():
    print_green("🛡️ Installing & configuring Fail2Ban…")
    run("apt-get update -y && apt-get install -y fail2ban || true")
    run("systemctl enable fail2ban || true")
    Path("/etc/fail2ban/jail.d").mkdir(parents=True, exist_ok=True)
    (Path("/etc/fail2ban/jail.d")/"wordpress-apache.conf").write_text(r"""[DEFAULT]
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
    """, encoding="utf-8")
    progress_tick()

    Path("/etc/fail2ban/filter.d").mkdir(parents=True, exist_ok=True)
    (Path("/etc/fail2ban/filter.d")/"apache-xmlrpc.conf").write_text(r"""[Definition]
    failregex = ^<HOST> - .* "POST /xmlrpc\.php HTTP/.*" 200
    ignoreregex =
    """, encoding="utf-8")
    (Path("/etc/fail2ban/filter.d")/"wordpress-login.conf").write_text(r"""[Definition]
    # Count repeated POSTs to wp-login.php with 200/302/403
    failregex = ^<HOST> - .* "(GET|POST) /wp-login\.php HTTP/.*" (200|302|403)
    ignoreregex =
    """, encoding="utf-8")
    progress_tick()

    run("systemctl restart fail2ban || true")
    run("systemctl status fail2ban --no-pager || true")

def undo_setup_fail2ban():
    print_yellow("Removing Fail2Ban jails and disabling service (best-effort)…")
    run("systemctl stop fail2ban || true")
    try:
        for p in [
            Path("/etc/fail2ban/jail.d/wordpress-apache.conf"),
            Path("/etc/fail2ban/filter.d/apache-xmlrpc.conf"),
            Path("/etc/fail2ban/filter.d/wordpress-login.conf"),
        ]:
            if p.exists():
                p.unlink()
    except Exception:
        pass
    run("systemctl disable fail2ban || true")

def secure_apache():
    print_green("🔐 Applying Apache hardening…")
    run("apt-get install -y apache2 || true")
    run("a2enmod headers >/dev/null 2>&1 || true")
    run("a2enmod rewrite >/dev/null 2>&1 || true")
    run("a2enmod security2 >/dev/null 2>&1 || true || echo")

    secconf = Path("/etc/apache2/conf-available/security.conf")
    if secconf.exists():
        _backup(secconf)
        run("sed -i 's/^\\s*ServerTokens.*/ServerTokens Prod/i' /etc/apache2/conf-available/security.conf || true")
        run("sed -i 's/^\\s*ServerSignature.*/ServerSignature Off/i' /etc/apache2/conf-available/security.conf || true")
    else:
        secconf.write_text("""ServerTokens Prod
ServerSignature Off
TraceEnable Off
""", encoding="utf-8")
        progress_tick()

    headers_conf = Path("/etc/apache2/conf-available/hardening-headers.conf")
    _backup(headers_conf) if headers_conf.exists() else None
    headers_conf.write_text("""<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
Header always set X-Frame-Options "SAMEORIGIN"
Header always set Referrer-Policy "strict-origin-when-cross-origin"
Header always set X-XSS-Protection "1; mode=block"
Header always set Permissions-Policy "geolocation=(), camera=(), microphone=()"
</IfModule>
""", encoding="utf-8")
    progress_tick()
    run("a2enconf hardening-headers >/dev/null 2>&1 || true")
    run("a2enconf security >/dev/null 2>&1 || true")

    mpm = Path("/etc/apache2/mods-available/mpm_prefork.conf")
    if mpm.exists():
        _backup(mpm)
        run("sed -i 's/^\\s*MaxRequestWorkers.*/MaxRequestWorkers 150/i' /etc/apache2/mods-available/mpm_prefork.conf || true")
        run("sed -i 's/^\\s*KeepAliveTimeout.*/KeepAliveTimeout 5/i' /etc/apache2/mods-available/mpm_prefork.conf || true")

    methods = Path("/etc/apache2/conf-available/hardening-methods.conf")
    _backup(methods) if methods.exists() else None
    methods.write_text("""<Directory "/var/www/">
    <LimitExcept GET POST HEAD>
        Require all denied
    </LimitExcept>
</Directory>
""", encoding="utf-8")
    progress_tick()
    run("a2enconf hardening-methods >/dev/null 2>&1 || true")
    run("systemctl reload apache2 || systemctl restart apache2 || true")

def undo_secure_apache():
    print_yellow("Restoring Apache configs from backups where available…")
    for src, bak in RUN_STATE["backups"]:
        psrc = Path(src)
        if psrc.as_posix().startswith("/etc/apache2/") and Path(bak).exists():
            shutil.copy2(bak, psrc)
    run("a2disconf hardening-headers || true")
    run("a2disconf hardening-methods || true")
    run("systemctl reload apache2 || true")

def deploy_htaccess(wp_dir: Path):
    print_green(f"📄 Deploying secure .htaccess to {wp_dir}…")
    ht = wp_dir/".htaccess"
    if ht.exists():
        shutil.copy2(ht, wp_dir/f".htaccess.bak.{int(dt.datetime.now().timestamp())}")
    progress_tick()
    ht.write_text(r"""# BEGIN WordPress
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
    <FilesMatch "\\.php$">
        Require all denied
    </FilesMatch>
</Directory>
""", encoding="utf-8")
    progress_tick()
    try:
        uid = pwd.getpwnam("www-data").pw_uid
        gid = grp.getgrnam("www-data").gr_gid
        os.chown(ht, uid, gid)
    except Exception:
        pass
    os.chmod(ht, 0o644)
    progress_tick()

def undo_deploy_htaccess(wp_dir: Path):
    ht = wp_dir/".htaccess"
    backups = sorted(wp_dir.glob(".htaccess.bak.*"))
    if backups:
        latest = backups[-1]
        print_yellow(f"Restoring .htaccess from {latest}…")
        shutil.copy2(latest, ht)
    else:
        warn("No .htaccess backup found to restore.")

def move_wp_config(wp_dir: Path, target_dir: Path):
    print_green(f"📦 Moving wp-config.php to {target_dir}…")
    target_dir.mkdir(parents=True, exist_ok=True)
    src = wp_dir/"wp-config.php"
    dst = target_dir/"wp-config.php"
    if not src.exists():
        error(f"wp-config.php not found in {wp_dir}")
        raise FileNotFoundError(str(src))
    shutil.copy2(src, wp_dir/f"wp-config.php.bak.{int(dt.datetime.now().timestamp())}")
    progress_tick()
    shutil.move(str(src), str(dst))
    try:
        os.chown(dst, 0, 0)  # root:root
    except Exception:
        pass
    os.chmod(dst, 0o640)
    progress_tick()
    stub = f"""<?php // Loader stub — keep outside-webroot config in a custom path.
define('WP_CONFIG_EXTERNAL', '{dst}');
if (file_exists(WP_CONFIG_EXTERNAL)) {{
    require_once WP_CONFIG_EXTERNAL;
}} else {{
    die('wp-config external file not found.');
}}
"""
    (wp_dir/"wp-config.php").write_text(stub, encoding="utf-8")
    try:
        uid = pwd.getpwnam("www-data").pw_uid
        gid = grp.getgrnam("www-data").gr_gid
        os.chown(wp_dir/"wp-config.php", uid, gid)
    except Exception:
        pass
    os.chmod(wp_dir/"wp-config.php", 0o640)
    progress_tick()

def undo_move_wp_config(wp_dir: Path, target_dir: Path):
    src_stub = wp_dir/"wp-config.php"
    real = target_dir/"wp-config.php"
    if real.exists():
        print_yellow("Moving wp-config.php back inside WordPress dir…")
        shutil.move(str(real), str(src_stub))
    else:
        warn("External wp-config.php not found; nothing to move back.")

def generate_log_report():
    out = Path("/var/log/wp_security_report.txt")
    print_green(f"📝 Generating security report at {out}…")
    content = []
    content.append("=== WordPress Security Report ===")
    content.append(dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    content.append("")

    content.append("[Apache]")
    try:
        a = subprocess.check_output("apache2 -v 2>/dev/null || httpd -v 2>/dev/null || echo 'Apache not found'", shell=True, text=True)
        content.append(a.strip())
    except Exception:
        content.append("Apache not found")
    content.append("")
    progress_tick()

    content.append("[Loaded Modules]")
    try:
        m = subprocess.check_output("apache2ctl -M 2>/dev/null || httpd -M 2>/dev/null || true", shell=True, text=True)
        content.append(m.strip())
    except Exception:
        pass
    content.append("")
    progress_tick()

    content.append("[UFW Status]")
    try:
        u = subprocess.check_output("ufw status verbose 2>/1 || echo 'UFW not available'", shell=True, text=True)
        content.append(u.strip())
    except Exception:
        content.append("UFW not available")
    content.append("")
    progress_tick()

    content.append("[Fail2Ban Status]")
    for cmd in [
        "systemctl is-active fail2ban 2>/dev/null || true",
        "fail2ban-client status 2>/dev/null || true",
        "fail2ban-client status apache-auth 2>/dev/null || true",
        "fail2ban-client status wordpress-login 2>/dev/null || true",
        "fail2ban-client status apache-xmlrpc 2>/dev/null || true",
    ]:
        try:
            s = subprocess.check_output(cmd, shell=True, text=True)
            content.append(s.strip())
        except Exception:
            pass
    content.append("")
    progress_tick()

    content.append("[/var/www perms]")
    try:
        p = subprocess.check_output("namei -l /var/www/html 2>/dev/null || true", shell=True, text=True)
        content.append(p.strip())
    except Exception:
        pass

    out.write_text("\n".join(content) + "\n", encoding="utf-8")
    os.chmod(out, 0o644)
    progress_tick()

def undo_generate_log_report():
    out = Path("/var/log/wp_security_report.txt")
    if out.exists():
        out.unlink()

def restart_apache():
    run("systemctl restart apache2 || true")

# ================================
# HARDEN workflow
# ================================

def harden_wordpress(apache_root: Path, wp_dir: Path, wp_config_new_path: Path):
    print_green("🔧 Starting WordPress hardening (built-in)…")
    steps = [
        Step("Configure firewall", do=configure_firewall, undo=undo_configure_firewall, expected_ops=10),
        Step("Install & configure Fail2Ban", do=setup_fail2ban, undo=undo_setup_fail2ban, expected_ops=6),
        Step("Secure Apache", do=secure_apache, undo=undo_secure_apache, expected_ops=10),
        Step("Deploy secure .htaccess", do=lambda: deploy_htaccess(wp_dir), undo=lambda: undo_deploy_htaccess(wp_dir), expected_ops=4),
        Step("Move wp-config.php", do=lambda: move_wp_config(wp_dir, wp_config_new_path), undo=lambda: undo_move_wp_config(wp_dir, wp_config_new_path), expected_ops=5),
        Step("Generate security report", do=generate_log_report, undo=undo_generate_log_report, expected_ops=6),
        Step("Restart Apache", do=restart_apache, undo=restart_apache, expected_ops=1),
    ]
    StageRunner("Hardening Stages", steps).run()
    print_green("✅ Hardening complete.")


# ================================
# UNINSTALL (PURGE)
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
        error("Unsupported system: no apt, dnf, or yum found.")
        sys.exit(1)

    # services
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

def mysql_exec_embedded(sql: str, root_pw: str):
    if not root_pw:
        run(f"mysql -u root --protocol=socket --batch --raw --execute \"{sql}\"")
    else:
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(f"[client]\nuser=root\npassword={root_pw}\nprotocol=socket\n")
            tf.flush()
            run(f"mysql --defaults-extra-file={tf.name} --batch --raw --execute \"{sql}\"")
        os.unlink(tf.name)

def mysqldump_embedded(db: str, outpath: str, root_pw: str):
    if not root_pw:
        run(f"mysqldump -u root --single-transaction --routines --triggers {db} > {outpath}")
    else:
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(f"[client]\nuser=root\npassword={root_pw}\nprotocol=socket\n")
            tf.flush()
            run(f"mysqldump --defaults-extra-file={tf.name} --single-transaction --routines --triggers {db} > {outpath} || true")
        os.unlink(tf.name)

def uninstall_menu():
    detect_pm_services()
    # Auto-detect WP dir
    wp_dir = None
    for cand in ["/var/www/html/wordpress", "/var/www/wordpress", "/srv/www/wordpress", "/var/www/html"]:
        pc = Path(cand)
        if (pc.is_dir() and (pc/"wp-admin").exists()) or (pc/"wp-config.php").exists():
            wp_dir = pc
            break
    if not wp_dir:
        wp_dir = Path("/var/www/html/wordpress")

    print()
    print(f"{BOLD}Choose uninstall mode:{RESET}")
    print(" 1) Remove WordPress content only (files + DB/user; keep apps)")
    print(" 2) Complete delete (apps + configs + WP files + DB/user)")
    print(" 3) Remove apps only (keep WP files + DB/user)")
    print()
    choice = input("Enter 1/2/3: ").strip()
    if choice == "1":
        MODE = "content-only"
    elif choice == "2":
        MODE = "complete"
    elif choice == "3":
        MODE = "apps-only"
    else:
        error("Invalid selection.")
        sys.exit(2)

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
        if DB_NAME in ("mysql","sys","performance_schema","information_schema"):
            error(f"Refusing to drop critical database '{DB_NAME}'.")
            sys.exit(3)
        if DB_USER == "root":
            error("Refusing to drop user 'root'.")
            sys.exit(3)

    print()
    warn(f"{BOLD}Plan:{RESET}")
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
        warn("Aborted.")
        return

    trash = TRASH_ROOT / str(int(time.time()))
    trash.mkdir(parents=True, exist_ok=True)

    def step_stop_services():
        if APACHE_SVC:
            log(f"Stopping Apache ({APACHE_SVC})…")
            run(f"systemctl stop {APACHE_SVC} || true")
        if SQL_SVC and remove_packages:
            log(f"Stopping database service ({SQL_SVC})…")
            run(f"systemctl stop {SQL_SVC} || true")

    def undo_stop_services():
        if APACHE_SVC:
            run(f"systemctl start {APACHE_SVC} || true")
        if SQL_SVC and remove_packages:
            run(f"systemctl start {SQL_SVC} || true")

    def step_remove_packages():
        if not remove_packages:
            return
        if PKG == "apt":
            if purge_packages:
                log("Purging Apache…")
                run("apt-get remove --purge -y apache2 apache2-utils apache2-bin || true")
                log("Purging MySQL/MariaDB…")
                run("apt-get remove --purge -y mysql-server mysql-client mariadb-server mariadb-client mysql-common mariadb-common || true")
                log("Purging PHP…")
                run("apt-get remove --purge -y 'php*' 'libapache2-mod-php*' || true")
            else:
                log("Removing Apache (keeping configs)…")
                run("apt-get remove -y apache2 apache2-utils apache2-bin || true")
                log("Removing MySQL/MariaDB (keeping configs/data)…")
                run("apt-get remove -y mysql-server mysql-client mariadb-server mariadb-client || true")
                log("Removing PHP (keeping configs)…")
                run("apt-get remove -y 'php*' 'libapache2-mod-php*' || true")
            log("Autoremove/autoclean…")
            run("apt-get -y autoremove || true")
            run("apt-get -y autoclean || true")
            if purge_packages:
                log("Removing data/config dirs (MySQL/MariaDB)…")
                run("rm -rf /etc/mysql /var/lib/mysql /var/lib/mariadb || true")
            if command_exists("add-apt-repository"):
                r = subprocess.run("grep -qi 'ppa.launchpadcontent.net/ondrej/php' /etc/apt/sources.list.d/*.list 2>/dev/null", shell=True)
                if r.returncode == 0:
                    log("Removing PPA:ondrej/php…")
                    run("add-apt-repository --remove -y ppa:ondrej/php || true")
        elif PKG in ("dnf", "yum"):
            PMBIN = f"{PKG} -y"
            log("Removing Apache/MySQL/PHP packages…")
            run(f"{PMBIN} remove httpd httpd-tools || true")
            run(f"{PMBIN} remove mysql-server mariadb-server mariadb || true")
            run(f"{PMBIN} remove 'php*' php-cli php-fpm mod_php || true")
            if PKG == "dnf":
                run("dnf autoremove -y || true")
                run("dnf clean all || true")
            else:
                run("yum autoremove -y || true")
                run("yum clean all || true")
            if purge_packages:
                log("Removing data/config dirs (MySQL/MariaDB)…")
                run("rm -rf /etc/my.cnf /etc/mysql /var/lib/mysql /var/lib/mariadb || true")

    def undo_remove_packages():
        warn("Package removals are not automatically re-installed by undo. Reinstall manually if needed.")

    def step_delete_wp_files():
        if MODE == "apps-only":
            return
        if Path(wp_dir).exists():
            dst = trash/"wordpress-files"
            log(f"Moving '{wp_dir}' to trash '{dst}'…")
            shutil.move(str(wp_dir), str(dst))
            progress_tick()
        for f in ["/var/www/html/wp-config.php", "/var/www/html/wp-config-sample.php"]:
            p = Path(f)
            if p.exists():
                dst = trash/p.name
                shutil.move(str(p), str(dst))
                progress_tick()
        if Path("/var/www/html").exists():
            log("Resetting ownership/perms on /var/www/html…")
            run("chown -R root:root /var/www/html")
            run("find /var/www/html -type d -exec chmod 755 {} +")
            run("find /var/www/html -type f -exec chmod 644 {} +")

    def undo_delete_wp_files():
        if (trash/"wordpress-files").exists():
            log("Restoring WordPress files from trash…")
            shutil.move(str(trash/"wordpress-files"), str(wp_dir))
        for name in ["wp-config.php", "wp-config-sample.php"]:
            p = trash/name
            if p.exists():
                shutil.move(str(p), f"/var/www/html/{name}")

    def step_drop_db():
        if MODE == "apps-only":
            return
        if not DB_NAME or not DB_USER:
            warn("DB name/user not provided; skipping DB drop.")
            return
        if BACKUP_SQL:
            log(f"Backing up database '{DB_NAME}' to '{BACKUP_SQL}'…")
            mysqldump_embedded(DB_NAME, BACKUP_SQL, MYSQL_ROOT_PASSWORD)
        log(f"Dropping database '{DB_NAME}' and user '{DB_USER}'@'localhost'…")
        mysql_exec_embedded(f"""
            SET sql_notes=0;
            DROP DATABASE IF EXISTS {DB_NAME};
            DROP USER IF EXISTS '{DB_USER}'@'localhost';
            FLUSH PRIVILEGES;
        """, MYSQL_ROOT_PASSWORD)

    def undo_drop_db():
        if BACKUP_SQL and Path(BACKUP_SQL).exists():
            warn("Attempting restore from backup SQL…")
            if MYSQL_ROOT_PASSWORD:
                with tempfile.NamedTemporaryFile("w", delete=False) as tf:
                    tf.write(f"[client]\nuser=root\npassword={MYSQL_ROOT_PASSWORD}\nprotocol=socket\n")
                    tf.flush()
                    run(f"mysql --defaults-extra-file={tf.name} < '{BACKUP_SQL}' || true")
                os.unlink(tf.name)
            else:
                run(f"mysql -u root < '{BACKUP_SQL}' || true")
        else:
            warn("No backup SQL available to restore.")

    steps = [
        Step("Stop services", do=step_stop_services, undo=undo_stop_services, expected_ops=2),
        Step("Remove packages", do=step_remove_packages, undo=undo_remove_packages,
             note="If chosen mode removes apps. Undo will NOT auto-reinstall packages.", expected_ops=10),
        Step("Delete WordPress files", do=step_delete_wp_files, undo=undo_delete_wp_files, expected_ops=5),
        Step("Drop database & user", do=step_drop_db, undo=undo_drop_db,
             note="If a backup path was provided, undo will attempt a restore.", expected_ops=3),
    ]

    StageRunner("Uninstall Stages", steps).run()
    print_green(f"Done. Uninstall mode '{MODE}' completed.")


# ================================
# INSTALL workflow (staged)
# ================================

def install_prereqs():
    run("apt-get update -y")
    run("apt-get install -y software-properties-common curl")

def undo_install_prereqs():
    run("apt-get remove -y software-properties-common curl")

def install_php():
    run("add-apt-repository -y ppa:ondrej/php")
    run("apt-get update -y")
    run("apt-get install -y php7.4 php7.4-mysql php7.4-curl php7.4-gd php7.4-mbstring php7.4-xml php7.4-zip php7.4-xmlrpc")

def undo_install_php():
    run("apt-get remove -y 'php7.4*'")
    run("add-apt-repository --remove -y ppa:ondrej/php")

def install_mysql():
    run("apt-get install -y mysql-server")
    # Secure MySQL installation
    mysql_secure_cmd = [
        "mysql",
        "-e",
        "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '';"
        "DELETE FROM mysql.user WHERE User='';"
        "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');"
        "DROP DATABASE IF EXISTS test;"
        "DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';"
        "FLUSH PRIVILEGES;"
    ]
    subprocess.run(mysql_secure_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def undo_install_mysql():
    run("apt-get remove -y mysql-server mysql-client")

def configure_mysql_wp(db_name, db_user, db_password):
    mysql_cmd = f"mysql -u root -e \"CREATE DATABASE IF NOT EXISTS {db_name}; CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_password}'; GRANT ALL PRIVILEGES ON {db_name}.* TO '{db_user}'@'localhost'; FLUSH PRIVILEGES;\""
    run(mysql_cmd)

def undo_configure_mysql_wp(db_name, db_user):
    mysql_cmd = f"mysql -u root -e \"DROP DATABASE IF EXISTS {db_name}; DROP USER IF EXISTS '{db_user}'@'localhost'; FLUSH PRIVILEGES;\""
    run(mysql_cmd)

def install_apache():
    run("apt-get install -y apache2")
    run("a2enmod rewrite")
    run("systemctl restart apache2")

def undo_install_apache():
    run("apt-get remove -y apache2 apache2-utils apache2-bin")

def download_wordpress(apache_root, wp_dir):
    if not wp_dir.exists():
        run("cd /tmp && curl -LO https://wordpress.org/latest.tar.gz")
        run("tar xzvf /tmp/latest.tar.gz -C /tmp")
        run(f"mv /tmp/wordpress {apache_root}/")
        run(f"chown -R www-data:www-data {wp_dir}")
        run(f"chmod -R 755 {wp_dir}")
        run("rm /tmp/latest.tar.gz")

def undo_download_wordpress(wp_dir):
    if wp_dir.exists():
        run(f"rm -rf {wp_dir}")

def configure_wp_config(wp_dir, db_name, db_user, db_password):
    wp_config = wp_dir / "wp-config.php"
    if not wp_config.exists():
        run(f"cp {wp_dir}/wp-config-sample.php {wp_config}")
    
    run(f"sed -i \"s/'DB_NAME', 'database_name_here'/'DB_NAME', '{db_name}'/g\" {wp_config}")
    run(f"sed -i \"s/'DB_USER', 'username_here'/'DB_USER', '{db_user}'/g\" {wp_config}")
    run(f"sed -i \"s/'DB_PASSWORD', 'password_here'/'DB_PASSWORD', '{db_password}'/g\" {wp_config}")

def undo_configure_wp_config(wp_dir):
    wp_config = wp_dir / "wp-config.php"
    if wp_config.exists():
        run(f"rm {wp_config}")

def install_menu():
    check_ports_80_443()
    print()
    user_choice = input("Do you want to continue with the script execution? (yes/no): ").strip().lower()
    if user_choice not in ("yes", "y"):
        print_red("❌ Script execution aborted by the user.")
        sys.exit(0)

    server_ip = input("Enter your server IP address: ").strip()
    db_name = input("Enter your database name: ").strip()
    db_user = input("Enter your database username: ").strip()
    db_password = getpass.getpass("Enter your database password: ")
    wp_password = getpass.getpass("Enter the WordPress database password (same as above unless different): ")
    if not wp_password:
        wp_password = db_password

    APACHE_ROOT = APACHE_ROOT_DEFAULT
    WP_DIR = WP_DIR_DEFAULT

    steps = [
        Step("Install prerequisites", do=install_prereqs, undo=undo_install_prereqs, expected_ops=2),
        Step("Install PHP", do=install_php, undo=undo_install_php, expected_ops=3),
        Step("Install MySQL server", do=install_mysql, undo=undo_install_mysql, expected_ops=2),
        Step("Create DB & user", do=lambda: configure_mysql_wp(db_name, db_user, db_password),
             undo=lambda: undo_configure_mysql_wp(db_name, db_user), expected_ops=1),
        Step("Install Apache", do=install_apache, undo=undo_install_apache, expected_ops=4),
        Step("Download WordPress", do=lambda: download_wordpress(APACHE_ROOT, WP_DIR),
             undo=lambda: undo_download_wordpress(WP_DIR), expected_ops=6),
        Step("Configure wp-config.php", do=lambda: configure_wp_config(WP_DIR, db_name, db_user, db_password),
             undo=lambda: undo_configure_wp_config(WP_DIR), expected_ops=4),
        Step("Restart Apache", do=restart_apache, undo=restart_apache, expected_ops=1),
    ]

    StageRunner("Installation Stages", steps).run()

    print_green("✅ WordPress installation is complete.")
    print(f"🌐 Visit: http://{server_ip}/wordpress")
    print(f"📌 If using a domain, ensure your DNS points to {server_ip}")
    print("🛠️ Finish setup in the browser interface.")


# ================================
# HARDEN workflow (menu wrapper)
# ================================

def harden_menu():
    wp_dir = input(f"WordPress directory? [{WP_DIR_DEFAULT}]: ").strip() or str(WP_DIR_DEFAULT)
    wp_cfg_path = input(f"Secure path to move wp-config.php? [{WP_CONFIG_NEW_PATH_DEFAULT}]: ").strip() or str(WP_CONFIG_NEW_PATH_DEFAULT)
    harden_wordpress(APACHE_ROOT_DEFAULT, Path(wp_dir), Path(wp_cfg_path))
    print_green("🗒️ A security report was saved to /var/log/wp_security_report.txt")


# ================================
# MAIN MENU
# ================================

def main_menu():
    print()
    print(f"{BOLD}WordPress Manager — choose an action:{RESET}")
    print(" 1) Install WordPress (LAMP + WP)")
    print(" 2) Harden existing WordPress (built-in)")
    print(" 3) Uninstall / Purge WordPress (interactive modes)")
    print(" 4) Exit")
    print()
    sel = input("Enter 1/2/3/4: ").strip()
    if sel == "1":
        StageRunner("Preflight", [Step("Root & logging setup", do=lambda: None, expected_ops=1)]).run()  # visual consistency
        install_menu()
    elif sel == "2":
        StageRunner("Preflight", [Step("Root & logging setup", do=lambda: None, expected_ops=1)]).run()
        harden_menu()
    elif sel == "3":
        StageRunner("Preflight", [Step("Root & logging setup", do=lambda: None, expected_ops=1)]).run()
        uninstall_menu()
    elif sel == "4":
        print("Bye.")
        sys.exit(0)
    else:
        error("Invalid selection.")
        sys.exit(2)


# ================================
# Entry
# ================================

def main():
    require_root()
    setup_logging()
    main_menu()


if __name__ == "__main__":
    main()
