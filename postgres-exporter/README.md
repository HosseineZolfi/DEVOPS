# PostgreSQL Exporter (Prometheus) — Setup Guide

This README explains how to expose metrics from a **host-installed PostgreSQL** instance using **postgres_exporter** and scrape them with **Prometheus**, based on the provided Docker Compose service.

> **Context**: PostgreSQL runs **on the VM**. The exporter runs in Docker with **host networking**, so it listens on the host at port **9187** by default.

---

## Prerequisites

- Ubuntu/Debian VM with sudo access
- **PostgreSQL** already installed and running on the VM
- Docker Engine + Docker Compose
- A PostgreSQL role (user) and password that the exporter will use

---

## 1) Install & prepare PostgreSQL on the host

Install (if you haven't already):

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install postgresql -y
```

Allow PostgreSQL to listen for remote/TCP connections (adjust versioned path as needed):

```bash
sudo vim /etc/postgresql/14/main/postgresql.conf
```

Uncomment and set:

```conf
listen_addresses = '*'
```

Authorize the exporter/Prometheus host in **pg_hba.conf**:

```bash
sudo vim /etc/postgresql/14/main/pg_hba.conf
```

Add **below** the existing IPv4 local connection line and replace `YOUR_IP` with the machine that will connect (the exporter container shares the host network, so you can also allow `127.0.0.1/32` if the exporter runs on the same VM):

```text
# IPv4 local connections:
host    all             all             127.0.0.1/32             scram-sha-256
host    all             all             YOUR_IP/32               scram-sha-256
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

---

## 2) Create a minimally‑privileged user for the exporter (recommended)

```bash
# become postgres and open psql
sudo -u postgres psql

-- inside psql:
CREATE USER metrics WITH PASSWORD 'strong_password';
GRANT pg_monitor TO metrics;   -- requires Postgres 10+
-- (optional) if pg_monitor is not available, grant SELECT on pg_catalog or required views
\q
```

> Using a dedicated user with `pg_monitor` is preferred over `postgres` superuser.

---

## 3) Docker Compose service (provided)

Create or update `docker-compose.yml` with the following service (kept exactly as requested):

```yaml
services:
  postgres-exporter:
    image: quay.io/prometheuscommunity/postgres-exporter
    environment:
      DATA_SOURCE_NAME: "postgresql://username:password@hostip:port/postgres?sslmode=disable"
    network_mode: host
    restart: always
```

### Configure `DATA_SOURCE_NAME`

Replace the placeholders:

- `username`: the PostgreSQL role (e.g., `metrics`)
- `password`: the role’s password
- `hostip`: use `127.0.0.1` if the exporter runs on the same VM as PostgreSQL (recommended with `network_mode: host`)
- `port`: PostgreSQL port (default `5432`)
- `postgres`: database name (you can keep `postgres` or specify another DB)

**Examples**

Same VM (common case):
```
DATA_SOURCE_NAME=postgresql://metrics:STRONG_PASS@127.0.0.1:5432/postgres?sslmode=disable
```

Remote DB:
```
DATA_SOURCE_NAME=postgresql://metrics:STRONG_PASS@YOUR_DB_IP:5432/postgres?sslmode=disable
```

> `network_mode: host` binds exporter port **9187** on the host. Make sure nothing else is using `9187`.

Start the service:

```bash
docker compose up -d
docker compose logs -f postgres-exporter
```

---

## 4) Add the exporter to Prometheus

Edit your `prometheus.yml` and add the job (note indentation):

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "postgres-exporter"
    static_configs:
      - targets: ["YOUR_EXPORTER_HOST:9187"]
```

- If Prometheus runs on the **same VM**, you can use `localhost:9187`.
- Otherwise, use the VM IP where the exporter is running.

Reload Prometheus or restart your stack to apply changes.

---

## 5) Verify metrics

From the VM (or any host that can reach the exporter):

```bash
curl http://localhost:9187/metrics      # if on the same VM
# or
curl http://YOUR_EXPORTER_HOST:9187/metrics
```

You should see Prometheus‑formatted metrics like `pg_up`, `pg_stat_*`, etc.

---

## Troubleshooting

- **Exporter starts but Prometheus shows target DOWN**  
  Check firewall/security groups for port `9187`. Validate the `targets` entry in `prometheus.yml`.

- **Exporter logs show authentication or permission errors**  
  Re‑check the `DATA_SOURCE_NAME` credentials and that the user exists. If using the `metrics` role, ensure it has `pg_monitor` (or the necessary SELECT privileges).

- **Cannot connect from exporter to DB**  
  Ensure `listen_addresses='*'` in `postgresql.conf`, and `pg_hba.conf` includes either `127.0.0.1/32` (same VM) or `YOUR_IP/32` as appropriate. Confirm PostgreSQL is listening on port `5432` (`ss -ltnp | grep 5432`).

- **Port conflict on 9187**  
  Because of `network_mode: host`, the exporter binds the host port directly. Free the port or run without host networking and map a port explicitly.

---

## Security Notes

- Prefer `127.0.0.1` in `DATA_SOURCE_NAME` when exporter and DB run on the same VM.  
- Use a strong password and a dedicated role (e.g., `metrics`) with **least privilege**.  
- Restrict network access to port `9187` if Prometheus is the only consumer.  
- Consider using TLS and/or placing Prometheus and the exporter on a private network.

---

## Summary

1) Prepare PostgreSQL to listen and allow connections (edit `postgresql.conf`, `pg_hba.conf`) →  
2) Create a minimally‑privileged user for metrics →  
3) Run the exporter with the exact Compose service above and set `DATA_SOURCE_NAME` →  
4) Add a Prometheus scrape job →  
5) Verify at `http://<host>:9187/metrics`.

All set! Your PostgreSQL metrics should now be visible in Prometheus.
