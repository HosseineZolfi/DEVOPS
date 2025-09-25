
# ELK Stack with Docker Compose

Spin up a local Elastic Stack (Elasticsearch, Logstash, Kibana — a.k.a. **ELK**) using Docker Compose.

> This README is tailored for the `elk-compose/` folder of this repository. It assumes a standard Compose layout with `docker-compose.yml`, optional `elasticsearch/`, `kibana/`, `logstash/` config subfolders, and a `.env` file for version/credentials.

---

## Table of contents
- [What you get](#what-you-get)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Configuration](#configuration)
  - [Environment (.env)](#environment-env)
  - [Service ports](#service-ports)
  - [Data volumes](#data-volumes)
  - [Heap size & JVM](#heap-size--jvm)
  - [Security](#security)
- [Common tasks](#common-tasks)
  - [Reset built‑in user passwords](#reset-built-in-user-passwords)
  - [Load sample data](#load-sample-data)
  - [Ship logs via TCP/Beats](#ship-logs-via-tcpbeats)
- [Troubleshooting](#troubleshooting)
- [Clean up](#clean-up)
- [Notes for production](#notes-for-production)
- [Credits](#credits)

---

## What you get

A minimal, local ELK stack suitable for development and demos:

- **Elasticsearch** (single node)
- **Kibana**
- **Logstash** (with a basic pipeline for TCP/Beats)

> Optional: If present in the project, per‑service configuration files are mounted from `elasticsearch/config/`, `kibana/config/`, and `logstash/pipeline/`.

---

## Prerequisites

- Docker Engine **20.10+** / Docker Desktop **4.x+**
- Docker Compose plugin **v2+** (`docker compose version`)
- >= **4 GB RAM** available to containers (2 GB minimum for a tiny demo)

---

## Quick start

From the `elk-compose/` directory:

```bash
# 0) (Optional) Copy and edit environment defaults
cp -n .env.example .env 2>/dev/null || true

# 1) Bring up the stack (foreground)
docker compose up

#    Or detached
# docker compose up -d
```

Once containers are healthy, open **Kibana**:

- URL: http://localhost:5601
- Default user: `elastic`
- Password: from your `.env` (see `ELASTIC_PASSWORD`), or as printed by the setup step (if your Compose defines one)

> If your Compose file defines a dedicated **setup** job/service, run it once before the first start:
>
> ```bash
> docker compose up setup
> ```

---

## Configuration

### Environment (.env)

Typical keys (your project may include a subset):

```ini
# Elastic Stack version for images
ELASTIC_VERSION=8.17.0

# Built‑in users (change these!)
ELASTIC_PASSWORD=changeme
KIBANA_SYSTEM_PASSWORD=changeme
LOGSTASH_INTERNAL_PASSWORD=changeme

# Kibana, Elasticsearch, Logstash ports (host side)
KIBANA_PORT=5601
ELASTICSEARCH_HTTP_PORT=9200
ELASTICSEARCH_TRANSPORT_PORT=9300
LOGSTASH_BEATS_PORT=5044
LOGSTASH_TCP_PORT=50000

# JVM heap (examples)
ES_JAVA_OPTS=-Xms1g -Xmx1g
LOGSTASH_JAVA_OPTS=-Xms512m -Xmx512m
KIBANA_MEMORY_LIMIT=1024m
```

> If your Compose uses different variable names, keep the semantics the same: version pinning, credentials, ports, and heap.

### Service ports

- **Elasticsearch**: `9200` (HTTP), `9300` (transport)
- **Kibana**: `5601`
- **Logstash**: `5044` (Beats), `50000` (TCP input), `9600` (monitoring)

> If you changed host mappings in `docker-compose.yml`, prefer those over the defaults above.

### Data volumes

Elasticsearch data is usually persisted via a named volume (e.g., `es-data`) or a host bind mount. This allows you to stop/recreate containers without losing indexed data or Kibana settings.

### Heap size & JVM

Adjust heap via env vars (examples above). As a rule of thumb for a single-node dev stack:

- **Elasticsearch**: 1–2 GB
- **Logstash**: 512 MB – 1 GB
- **Kibana**: 512 MB – 1 GB

> Don’t set ES heap larger than 50% of the Docker memory limit. Ensure `bootstrap.memory_lock=true` and proper ulimits if your Compose file enables them.

### Security

For local development you can start with built‑in users and passwords from `.env`. For anything beyond demos:

- Change all default passwords.
- Consider enabling TLS and generating Kibana encryption keys.
- Avoid using the `elastic` super‑user for applications; create least‑privilege users.

---

## Common tasks

### Reset built‑in user passwords

Inside the Elasticsearch container:

```bash
# Elastic (superuser)
docker compose exec elasticsearch   bin/elasticsearch-reset-password --batch --user elastic

# Kibana system
docker compose exec elasticsearch   bin/elasticsearch-reset-password --batch --user kibana_system

# Logstash internal
docker compose exec elasticsearch   bin/elasticsearch-reset-password --batch --user logstash_internal
```

Update the new secrets back into `.env` and any referenced config files.

### Load sample data

In Kibana → *Home* → *Add data*, load any sample datasets (e.g., eCommerce). Alternatively, ingest your own logs via Logstash (below).

### Ship logs via TCP/Beats

**TCP input** (simple demo):

```bash
# BSD netcat
cat /path/to/logfile.log | nc -q0 localhost 50000

# GNU netcat
cat /path/to/logfile.log | nc -c localhost 50000

# nmap ncat
cat /path/to/logfile.log | nc --send-only localhost 50000
```

**Beats input**: point Filebeat/Metricbeat to Logstash on `localhost:5044` (or directly to Elasticsearch for very simple dev use‑cases).

---

## Troubleshooting

- **Kibana 503 / not ready** → Give it ~60–90s on first boot. Check `docker compose logs kibana`.
- **Elasticsearch red/bootloop** → Lower heap or raise Docker memory limit; ensure disk space; remove old data volume if you really want a clean slate.
- **Auth failures** → Reset passwords (see above) and update `.env` and config mounts.
- **Port conflicts** → Change host ports in `.env`/`docker-compose.yml`.
- **Linux perms** → Make sure your user can talk to Docker (`docker` group), and that bind‑mounted paths are readable by the container UID/GID.

---

## Clean up

Stop containers, remove them, and **wipe data volumes** (⚠️ destructive):

```bash
docker compose down -v
```

> If your stack uses a separate `setup` profile/service, include it during teardown to remove its volumes as well:
>
> ```bash
> docker compose --profile=setup down -v
> ```

---

## Notes for production

This setup is intended for **development**. For production:

- Run multi‑node Elasticsearch with proper discovery and quorum.
- Enable TLS (HTTP & transport), rotate credentials, and use dedicated service accounts.
- Size JVM heap and ulimits correctly; pin CPU/memory.
- Externalize persistent storage with snapshots/backup.
- Use infrastructure automation (Ansible/Terraform/Kubernetes) and observability.

---

## Credits

This Compose layout and commands follow widely‑used community practices for running the Elastic Stack in containers. See the upstream Elastic documentation and popular reference repositories for further details.
