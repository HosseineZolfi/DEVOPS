# PostgreSQL + Postgres Exporter — Setup Guide

This guide walks you through preparing a host-installed **PostgreSQL** instance and exposing its metrics via **postgres_exporter**, then scraping those metrics with **Prometheus**.

> **Scope:** PostgreSQL is installed **on the VM**, not in Docker. The exporter runs (e.g., via Docker Compose), and Prometheus scrapes it.

---

## Prerequisites

- Ubuntu/Debian VM with sudo access  
- Docker Compose stack that includes **postgres_exporter** (or plan to run it)  
- The VM’s public/private IP (referenced below as `YOUR_IP`)

---

## 1) Install PostgreSQL on the VM

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install postgresql -y
```

> Package name is **postgresql** (not “postgressql”).

---

## 2) Allow PostgreSQL to listen for remote connections

Edit `postgresql.conf` (adjust versioned path if needed):

```bash
sudo vim /etc/postgresql/14/main/postgresql.conf
```

Uncomment and set:

```conf
listen_addresses = '*'
```

---

## 3) Permit your client/exporter IP in `pg_hba.conf`

Edit `pg_hba.conf`:

```bash
sudo vim /etc/postgresql/14/main/pg_hba.conf
```

Find the block:

```text
# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256
```

Add a line **below it** that allows your Prometheus/exporter host to connect (replace `YOUR_IP`):

```text
host    all             all             YOUR_IP/32               scram-sha-256
```

**Example final block:**
```text
# IPv4 local connections:
host    all             all             127.0.0.1/32             scram-sha-256
host    all             all             YOUR_IP/32               scram-sha-256
```

> Use `scram-sha-256` unless you have a specific reason to use another method.

---

## 4) Restart (or reload) PostgreSQL

```bash
sudo systemctl restart postgresql
# or, if only config changed and you want fewer interruptions:
# sudo systemctl reload postgresql
```

Optional quick check:

```bash
ss -ltnp | grep 5432
```

---

## 5) Configure **postgres_exporter** credentials

Your exporter needs valid DB credentials (user & password) with permission to read metrics.  
If you use Docker Compose for the exporter, ensure its env vars (e.g., `DATA_SOURCE_NAME` or user/password vars) match a valid PostgreSQL role.

**Create/adjust a passworded role (example):**
```bash
# become postgres user
sudo -u postgres psql

-- inside psql:
ALTER USER yourusername WITH PASSWORD 'yourpassword';
\q
```

> If your exporter isn’t returning data, double-check these credentials in your docker-compose file.

---

## 6) Add the exporter target to Prometheus

Update your `prometheus.yml` (indentation matters):

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['YOUR_IP:9187']   # replace with the exporter host:port
```

Reload Prometheus or restart your stack so it picks up the new config.

---

## 7) Verify metrics

From the host that can reach the exporter:

```bash
curl http://localhost:9187/metrics      # if you’re on the same host
# or
curl http://YOUR_IP:9187/metrics        # from another machine
```

You should see Prometheus-formatted metrics output.

---

## 8) Connect to PostgreSQL (manual checks)

```bash
# option A: via local system postgres account
sudo -u postgres psql

# option B: remote/local TCP connection
psql -U postgres -h YOUR_IP -p 5432
```

If needed, change a user’s password (inside `psql`):

```sql
ALTER USER yourusername WITH PASSWORD 'yourpassword';
```

---

## Troubleshooting

- **Exporter up, but no metrics in Prometheus:**  
  Confirm the `prometheus.yml` target IP/port and that the job name is correct.
- **Exporter returns auth errors:**  
  Role/password mismatch. Re-check the exporter env vars and `pg_hba.conf` entry (CIDR and auth method).
- **Cannot connect remotely:**  
  Verify `listen_addresses='*'`, `pg_hba.conf` includes `YOUR_IP/32`, and any firewalls (ufw/security groups) allow `5432` and exporter port `9187`.
- **YAML issues:**  
  Ensure proper indentation under `scrape_configs` (list items start with `-`).

---

## Security Notes

- Limit access strictly: use a specific `YOUR_IP/32` or your Prometheus node’s IP rather than `0.0.0.0/0`.  
- Use strong passwords and consider TLS if traversing untrusted networks.  
- Prefer a minimally-privileged role for the exporter.

---

## Summary

1) Install PostgreSQL → 2) enable remote listen → 3) grant IP in `pg_hba.conf` → 4) restart PostgreSQL →  
5) ensure exporter credentials → 6) add Prometheus job → 7) `curl` metrics → 8) adjust users as needed.

You’re set to monitor PostgreSQL with Prometheus!
