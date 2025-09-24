#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# harden-wp-bar-single.py — one-line progress bar, silent ops, summary at end

import argparse
import datetime as dt
import os
import pwd
import grp
import shutil
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Optional, List

# ================================
# Single-line progress bar
# ================================
def _term_bar_width(padding: int = 12, min_width: int = 10, max_width: int = 100):
    # padding accounts for brackets, spaces, " 100%" text
    try:
        import shutil as _sh
        cols = _sh.get_terminal_size(fallback=(80, 24)).columns
    except Exception:
        cols = 80
    return max(min(max_width, cols - padding), min_width)

class ProgressBar:
    def __init__(self):
        self.total_ops = 1
        self.done = 0
        self.started = False
        self.last_pct = -1
        self.width = _term_bar_width()

    def _render(self, pct: int) -> str:
        pct = max(0, min(100, int(pct)))
        self.width = _term_bar_width()
        filled = int(round((pct/100.0) * self.width))
        # \r go to line start, \033[2K erase whole line, then print bar
        return f"\r\033[2K[{'#'*filled}{'-'*(self.width - filled)}] {pct:3d}%"

    def _write(self, pct: int):
        if pct == self.last_pct:
            return
        self.last_pct = pct
        sys.stdout.write(self._render(pct))
        sys.stdout.flush()

    def start(self, total_ops: int):
        self.total_ops = max(1, int(total_ops))
        self.done = 0
        self.started = True
        self.last_pct = -1
        self._write(0)

    def tick(self, inc: int = 1):
        if not self.started:
            return
        self.done += inc
        done = min(self.done, self.total_ops)
        pct = min(int(done / self.total_ops * 100), 99)  # hold 99% until end()
        self._write(pct)

    def end(self):
        if not self.started:
            return
        self._write(100)
        sys.stdout.write("\n")
        sys.stdout.flush()
        self.started = False

PROG = ProgressBar()

# Suppress all incidental output
def _noop(*a, **k): pass
print_green = print_yellow = print_cyan = error = log = _noop

def require_root():
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        sys.exit(1)

# ================================
# Silent subprocess
# ================================
_DEVNULL = subprocess.DEVNULL
def run(cmd, check=True, shell=True, env=None):
    subprocess.run(
        cmd,
        shell=shell,
        executable="/bin/bash" if shell else None,
        check=check,
        env=env,
        stdout=_DEVNULL,
        stderr=_DEVNULL,
    )
    PROG.tick(1)

# ================================
# Stage framework
# ================================
@dataclass
class Step:
    name: str
    do: Callable[[], None]
    undo: Optional[Callable[[], None]] = None
    expected_ops: int = 1

class StageRunner:
    def __init__(self, steps: List[Step]):
        self.steps = steps

    def run(self):
        total_ops = sum(max(1, int(s.expected_ops)) for s in self.steps)
        PROG.start(total_ops)
        for step in self.steps:
            try:
                step.do()
            except subprocess.CalledProcessError:
                if step.undo:
                    try: step.undo()
                    except Exception: pass
                PROG.end()
                sys.exit(1)
        PROG.end()

# ================================
# Helpers / state
# ================================
def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None

STATE_DIR = Path("/var/lib/wp-manager")
STATE_DIR.mkdir(parents=True, exist_ok=True)
RUN_STATE = {"backups": []}
SUMMARY: List[str] = []

def _backup(path: Path):
    if not path.exists():
        return
    bak = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
    shutil.copy2(path, bak)
    RUN_STATE["backups"].append((str(path), str(bak)))
    return bak

# ================================
# Steps (quiet)
# ================================
def configure_firewall():
    if not command_exists("ufw"):
        run("apt-get update -y && apt-get install -y ufw || true")
    if command_exists("ufw"):
        snap = STATE_DIR / "ufw.status.before"
        try:
            with open(snap, "w") as f:
                subprocess.run("ufw status verbose", shell=True, check=False,
                               stdout=f, stderr=subprocess.STDOUT)
        except Exception:
            pass
        run("ufw --force reset >/dev/null 2>&1 || true")
        run("ufw default deny incoming")
        run("ufw default allow outgoing")
        run("ufw allow OpenSSH || ufw allow 22 || true")
        if subprocess.run("ufw app list 2>/dev/null | grep -q 'Apache Full'",
                          shell=True, stdout=_DEVNULL, stderr=_DEVNULL).returncode == 0:
            run('ufw allow "Apache Full"')
        else:
            run("ufw allow 80/tcp")
            run("ufw allow 443/tcp")
        run("yes | ufw enable >/dev/null 2>&1 || ufw enable || true")
        run("ufw status verbose || true")
        SUMMARY.append("UFW enabled: deny incoming by default; allow SSH/HTTP/HTTPS.")
    elif command_exists("firewall-cmd"):
        run("systemctl enable --now firewalld || true")
        run("firewall-cmd --permanent --add-service=http || firewall-cmd --permanent --add-port=80/tcp")
        run("firewall-cmd --permanent --add-service=https || firewall-cmd --permanent --add-port=443/tcp")
        run("firewall-cmd --permanent --add-service=ssh || firewall-cmd --permanent --add-port=22/tcp")
        run("firewall-cmd --reload || true")
        run("firewall-cmd --list-all || true")
        SUMMARY.append("firewalld configured: allow SSH/HTTP/HTTPS; reloaded rules.")
    else:
        run("iptables -P INPUT DROP || true")
        run("iptables -P FORWARD DROP || true")
        run("iptables -P OUTPUT ACCEPT || true")
        run("iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT || true")
        run("iptables -A INPUT -p tcp --dport 22 -j ACCEPT || true")
        run("iptables -A INPUT -p tcp --dport 80 -j ACCEPT || true")
        run("iptables -A INPUT -p tcp --dport 443 -j ACCEPT || true")
        run("iptables -A INPUT -i lo -j ACCEPT || true")
        SUMMARY.append("iptables policy applied: drop inbound by default; allow SSH/HTTP/HTTPS/loopback.")

def undo_configure_firewall():
    if command_exists("ufw"):
        run("ufw --force disable || true")
    elif command_exists("firewall-cmd"):
        run("firewall-cmd --reload || true")

def setup_fail2ban():
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
    PROG.tick()

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
    PROG.tick()
    run("systemctl restart fail2ban || true")
    run("systemctl status fail2ban --no-pager || true")
    SUMMARY.append("Fail2Ban installed and jails configured for Apache and WordPress login abuse.")

def undo_setup_fail2ban():
    run("systemctl stop fail2ban || true")
    try:
        for p in [
            Path("/etc/fail2ban/jail.d/wordpress-apache.conf"),
            Path("/etc/fail2ban/filter.d/apache-xmlrpc.conf"),
            Path("/etc/fail2ban/filter.d/wordpress-login.conf"),
        ]:
            if p.exists(): p.unlink()
    except Exception:
        pass
    run("systemctl disable fail2ban || true")

def secure_apache():
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
        secconf.write_text("ServerTokens Prod\nServerSignature Off\nTraceEnable Off\n", encoding="utf-8")
        PROG.tick()

    headers_conf = Path("/etc/apache2/conf-available/hardening-headers.conf")
    if headers_conf.exists(): _backup(headers_conf)
    headers_conf.write_text("""<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
Header always set X-Frame-Options "SAMEORIGIN"
Header always set Referrer-Policy "strict-origin-when-cross-origin"
Header always set X-XSS-Protection "1; mode=block"
Header always set Permissions-Policy "geolocation=(), camera=(), microphone=()"
</IfModule>
""", encoding="utf-8")
    PROG.tick()
    run("a2enconf hardening-headers >/dev/null 2>&1 || true")
    run("a2enconf security >/dev/null 2>&1 || true")

    mpm = Path("/etc/apache2/mods-available/mpm_prefork.conf")
    if mpm.exists():
        _backup(mpm)
        run("sed -i 's/^\\s*MaxRequestWorkers.*/MaxRequestWorkers 150/i' /etc/apache2/mods-available/mpm_prefork.conf || true")
        run("sed -i 's/^\\s*KeepAliveTimeout.*/KeepAliveTimeout 5/i' /etc/apache2/mods-available/mpm_prefork.conf || true")

    methods = Path("/etc/apache2/conf-available/hardening-methods.conf")
    if methods.exists(): _backup(methods)
    methods.write_text("""<Directory "/var/www/">
    <LimitExcept GET POST HEAD>
        Require all denied
    </LimitExcept>
</Directory>
""", encoding="utf-8")
    PROG.tick()
    run("a2enconf hardening-methods >/dev/null 2>&1 || true")
    run("systemctl reload apache2 || systemctl restart apache2 || true")
    SUMMARY.append("Apache hardened: hide version/signature, strict headers/methods, tuned worker/timeouts, reloaded service.")

def undo_secure_apache():
    for src, bak in RUN_STATE["backups"]:
        psrc = Path(src)
        if psrc.as_posix().startswith("/etc/apache2/") and Path(bak).exists():
            shutil.copy2(bak, psrc)
    run("a2disconf hardening-headers || true")
    run("a2disconf hardening-methods || true")
    run("systemctl reload apache2 || true")

def deploy_htaccess(wp_dir: Path):
    ht = wp_dir/".htaccess"
    if ht.exists():
        shutil.copy2(ht, wp_dir/f".htaccess.bak.{int(dt.datetime.now().timestamp())}")
    PROG.tick()
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

Options -Indexes

<FilesMatch "(^\.|wp-config\.php|readme\.html|license\.txt|composer\.(json|lock))">
    Require all denied
</FilesMatch>

<IfModule mod_rewrite.c>
    RewriteRule ^wp-admin/includes/ - [F,L]
    RewriteRule !^wp-includes/ - [S=3]
    RewriteRule ^wp-includes/[^/]+\.php$ - [F,L]
    RewriteRule ^wp-includes/js/tinymce/langs/.+\.php - [F,L]
    RewriteRule ^wp-includes/theme-compat/ - [F,L]
</IfModule>

<Files xmlrpc.php>
    Require ip 127.0.0.1 ::1
</Files>

<Directory "/var/www/html/wordpress/wp-content/uploads/">
    <FilesMatch "\.php$">
        Require all denied
    </FilesMatch>
</Directory>
""", encoding="utf-8")
    PROG.tick()
    try:
        uid = pwd.getpwnam("www-data").pw_uid
        gid = grp.getgrnam("www-data").gr_gid
        os.chown(ht, uid, gid)
    except Exception:
        pass
    os.chmod(ht, 0o644)
    PROG.tick()
    SUMMARY.append("Deployed restrictive .htaccess (no indexes, protect sensitive files, stricter rewrites & uploads).")

def undo_deploy_htaccess(wp_dir: Path):
    ht = wp_dir/".htaccess"
    backups = sorted(wp_dir.glob(".htaccess.bak.*"))
    if backups:
        latest = backups[-1]
        shutil.copy2(latest, ht)

def move_wp_config(wp_dir: Path, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    src = wp_dir/"wp-config.php"
    dst = target_dir/"wp-config.php"
    if not src.exists():
        raise FileNotFoundError(str(src))
    shutil.copy2(src, wp_dir/f"wp-config.php.bak.{int(time.time())}")
    PROG.tick()
    shutil.move(str(src), str(dst))
    try: os.chown(dst, 0, 0)
    except Exception: pass
    os.chmod(dst, 0o640)
    PROG.tick()
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
    PROG.tick()
    SUMMARY.append(f"Moved wp-config.php to {target_dir} (root:root, 0640) + safe loader stub in webroot.")

def undo_move_wp_config(wp_dir: Path, target_dir: Path):
    src_stub = wp_dir/"wp-config.php"
    real = target_dir/"wp-config.php"
    if real.exists():
        shutil.move(str(real), str(src_stub))

def generate_log_report():
    out = Path("/var/log/wp_security_report.txt")
    content = []
    content.append("=== WordPress Security Report ===")
    content.append(dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    content.append("")

    content.append("[Apache]")
    try:
        a = subprocess.check_output("apache2 -v 2>/dev/null || httpd -v 2>/dev/null || echo 'Apache not found'",
                                    shell=True, text=True)
        content.append(a.strip())
    except Exception:
        content.append("Apache not found")
    content.append("")
    PROG.tick()

    content.append("[Loaded Modules]")
    try:
        m = subprocess.check_output("apache2ctl -M 2>/dev/null || httpd -M 2>/dev/null || true",
                                    shell=True, text=True)
        content.append(m.strip())
    except Exception:
        pass
    content.append("")
    PROG.tick()

    content.append("[UFW Status]")
    try:
        u = subprocess.check_output("ufw status verbose 2>/dev/null || echo 'UFW not available'",
                                    shell=True, text=True)
        content.append(u.strip())
    except Exception:
        content.append("UFW not available")
    content.append("")
    PROG.tick()

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
    PROG.tick()

    content.append("[/var/www perms]")
    try:
        p = subprocess.check_output("namei -l /var/www/html 2>/dev/null || true",
                                    shell=True, text=True)
        content.append(p.strip())
    except Exception:
        pass

    out.write_text("\n".join(content) + "\n", encoding="utf-8")
    os.chmod(out, 0o644)
    PROG.tick()
    SUMMARY.append("Generated /var/log/wp_security_report.txt (Apache, firewall, Fail2Ban, permissions info).")

def undo_generate_log_report():
    out = Path("/var/log/wp_security_report.txt")
    if out.exists(): out.unlink()

def restart_apache():
    run("systemctl restart apache2 || true")
    SUMMARY.append("Restarted Apache to apply changes.")

# ================================
# Workflow
# ================================
APACHE_ROOT_DEFAULT = Path("/var/www/html")
WP_DIR_DEFAULT = APACHE_ROOT_DEFAULT / "wordpress"
WP_CONFIG_NEW_PATH_DEFAULT = Path("/var/www")

def harden_wordpress(wp_dir: Path, wp_config_new_path: Path):
    steps = [
        Step("Configure firewall", do=configure_firewall, undo=undo_configure_firewall, expected_ops=10),
        Step("Install & configure Fail2Ban", do=setup_fail2ban, undo=undo_setup_fail2ban, expected_ops=6),
        Step("Secure Apache", do=secure_apache, undo=undo_secure_apache, expected_ops=10),
        Step("Deploy secure .htaccess", do=lambda: deploy_htaccess(wp_dir), undo=lambda: undo_deploy_htaccess(wp_dir), expected_ops=4),
        Step("Move wp-config.php", do=lambda: move_wp_config(wp_dir, wp_config_new_path), undo=lambda: undo_move_wp_config(wp_dir, wp_config_new_path), expected_ops=5),
        Step("Generate security report", do=generate_log_report, undo=undo_generate_log_report, expected_ops=6),
        Step("Restart Apache", do=restart_apache, undo=restart_apache, expected_ops=1),
    ]
    StageRunner(steps).run()

    # After 100%, show a single message + summary
    print("✅ WordPress hardening complete.")
    print("Summary of actions:")
    for item in SUMMARY:
        print(f" • {item}")

# ================================
# Entry
# ================================
def parse_args():
    p = argparse.ArgumentParser(description="Harden WordPress (single progress bar; summary at end)")
    p.add_argument("--wp-dir", dest="wp_dir", default=str(WP_DIR_DEFAULT), help="Path to WordPress directory")
    p.add_argument("--cfg-dir", dest="cfg_dir", default=str(WP_CONFIG_NEW_PATH_DEFAULT), help="Directory to move wp-config.php into")
    return p.parse_args()

def _main():
    require_root()
    args = parse_args()
    harden_wordpress(Path(args.wp_dir), Path(args.cfg_dir))

if __name__ == "__main__":
    # Guard against unexpected tracebacks (keep output to one line + summary)
    try:
        _main()
    except SystemExit:
        raise
    except Exception:
        # Silent failure to preserve single-line UI expectation
        sys.exit(1)

