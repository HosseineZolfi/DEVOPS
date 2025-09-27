# Nexus Repository Manager (Docker Compose)

This folder runs **Sonatype Nexus Repository Manager 3** using Docker Compose with persistent storage. It’s ideal for local development, caching remote registries, and hosting private artifact repositories (Docker, Maven, npm, PyPI, etc.).

> This README is written for the `nexus/` directory in this repo. If your actual files differ, keep the same flow but match service names, ports, and volume paths from your `docker-compose.yml` and `.env`.

---

## Table of Contents
- [What’s included](#whats-included)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Configuration](#configuration)
  - [Environment (.env)](#environment-env)
  - [Service ports](#service-ports)
  - [Data volume](#data-volume)
  - [Java heap & JVM options](#java-heap--jvm-options)
- [First-time setup](#first-time-setup)
- [Repositories you can add](#repositories-you-can-add)
  - [Docker registries](#docker-registries)
  - [Maven, npm, PyPI, etc.](#maven-npm-pypi-etc)
- [Use Nexus as Docker mirror/registry](#use-nexus-as-docker-mirrorregistry)
- [Backup & restore](#backup--restore)
- [Troubleshooting](#troubleshooting)
- [Clean up](#clean-up)
- [Notes for production](#notes-for-production)

---

## What’s included

A single Nexus Repository 3 service, typically with:

- **Image**: `sonatype/nexus3`  
- **Ports**: `8081` (UI/API). Optional additional host ports for Docker registries if you expose them directly.  
- **Persistent data**: mounted under `/nexus-data`

Your `docker-compose.yml` usually looks similar to:

```yaml
services:
  nexus:
    image: sonatype/nexus3:latest
    container_name: nexus
    ports:
      - "${NEXUS_PORT:-8081}:8081"
      # (Optional) publish Docker repo ports if you configure them in Nexus
      # - "${NEXUS_DOCKER_HOSTED_PORT:-5000}:5000"
      # - "${NEXUS_DOCKER_GROUP_PORT:-5001}:5001"
      # - "${NEXUS_DOCKER_PROXY_PORT:-5002}:5002"
    volumes:
      - ${NEXUS_DATA:-./nexus-data}:/nexus-data
    restart: unless-stopped
```

---

## Prerequisites

- Docker Engine **20.10+** / Docker Desktop **4.x+**
- Docker Compose plugin **v2+**
- ~**2–4 GB RAM** free (Nexus needs ~2 GB for comfortable dev usage)

---

## Quick start

From the `nexus/` directory:

```bash
# 0) (Optional) copy env defaults
cp -n .env.example .env 2>/dev/null || true

# 1) bring up the service
docker compose up -d

# 2) watch logs (first boot can take ~1–2 minutes)
docker compose logs -f nexus
```

Open the UI at **http://localhost:8081** (or your mapped `NEXUS_PORT`).

---

## Configuration

### Environment (.env)

Typical keys:

```ini
# Host ports
NEXUS_PORT=8081
# Optional if you plan to publish Docker repos directly on host ports
NEXUS_DOCKER_HOSTED_PORT=5000
NEXUS_DOCKER_GROUP_PORT=5001
NEXUS_DOCKER_PROXY_PORT=5002

# Data path
NEXUS_DATA=./nexus-data

# JVM (optional – tune for your machine)
INSTALL4J_ADD_VM_PARAMS="-Xms1g -Xmx2g -XX:MaxDirectMemorySize=1g -Djava.util.prefs.userRoot=/nexus-data"
```

> Ensure `.env` names match those referenced in your `docker-compose.yml`.

### Service ports

- **8081/tcp** → Nexus UI & REST API
- Optional host ports for **Docker registries** (if you configure them): e.g., `5000`, `5001`, `5002`

### Data volume

All Nexus state lives under `/nexus-data`. In Compose, that maps to `./nexus-data` (bind mount) or a named volume. Keep this directory **persistent** and **backed up**.

### Java heap & JVM options

You can size memory via `INSTALL4J_ADD_VM_PARAMS`. For dev boxes 1–2 GB heap is typical. Increase if you host many repos or large indexes.

---

## First-time setup

1. **Retrieve admin password** (auto-generated on first run):

   ```bash
   # if using bind mount
   cat ./nexus-data/admin.password

   # or via container
   docker compose exec nexus cat /nexus-data/admin.password
   ```

2. Log in at **http://localhost:8081** with user `admin` and the password above.  
3. Change the admin password and (optionally) enable anonymous access.  
4. (Optional) Configure a **reverse proxy** (Nginx/Traefik/Caddy) and TLS in front of Nexus.

---

## Repositories you can add

### Docker registries

In the UI → **Repositories**:

- **docker (hosted)**: your private push/pull. Choose a unique **HTTP port** (e.g., `5000`) and expose it on the host if you want to reach it directly.  
- **docker (proxy)**: cache Docker Hub (`https://registry-1.docker.io`) or other registries.  
- **docker (group)**: combine hosted + proxy under one endpoint.

> When exposing Docker repos over **HTTP** on Linux, configure your Docker daemon with `insecure-registries` for that host:port, or terminate TLS at a reverse proxy and use **HTTPS**.

### Maven, npm, PyPI, etc.

Create **hosted**, **proxy**, and **group** repos as needed. Typical patterns:

- `maven-central` (proxy), `maven-releases` (hosted), `maven-snapshots` (hosted), `maven-all` (group)  
- `npmjs` (proxy), `npm-private` (hosted), `npm-group` (group)  
- `pypi-proxy` (proxy), `pypi-internal` (hosted), `pypi-group` (group)

Point your build tools at the **group** endpoints for simpler configuration.

---

## Use Nexus as Docker mirror/registry

**Docker daemon mirror** (use when you create a Docker **proxy** or **group** on port, e.g., `5001`):

`/etc/docker/daemon.json`:

```json
{
  "registry-mirrors": ["http://localhost:5001"],
  "insecure-registries": ["localhost:5000","localhost:5001","localhost:5002"]
}
```

Then reload Docker:

```bash
sudo systemctl restart docker
```

> Prefer HTTPS in real environments (terminate TLS at a proxy and use `https://nexus.example.com` instead).

---

## Backup & restore

- **Backup**: stop Nexus and archive `./nexus-data`:

  ```bash
  docker compose down
  tar -czf nexus-data-backup.tgz ./nexus-data
  ```

- **Restore**: extract backup, then `docker compose up -d`.

> For large instances, review Sonatype backup guidance and consider blob store snapshots.

---

## Troubleshooting

- **Slow startup / “Not initialized yet”** → First run may take 1–3 minutes. Check `docker compose logs -f nexus`.
- **Permission errors on `/nexus-data`** → Ensure the host path is writable by container UID/GID (often **200:200**):  
  `sudo chown -R 200:200 ./nexus-data`
- **Port conflicts** → Adjust `NEXUS_PORT` (and any Docker repo ports) in `.env` and `docker-compose.yml`.
- **Out of memory / GC pressure** → Increase heap in `INSTALL4J_ADD_VM_PARAMS`.
- **Lost admin password** → See Sonatype docs for password reset; if it’s a brand‑new instance, you can remove `admin.password` to regenerate (not for existing configured instances).

---

## Clean up

```bash
# stop and remove the container
docker compose down

# remove data too (⚠️ destructive)
docker compose down -v
```

---

## Notes for production

- Put Nexus behind an **HTTPS** reverse proxy with authentication.  
- Use external storage and regular **backups** of `/nexus-data`.  
- Pin image versions (e.g., `sonatype/nexus3:3.68.1`) for reproducibility.  
- Size JVM heap and enable monitoring.  
- Restrict anonymous access and enforce repository roles/permissions.
