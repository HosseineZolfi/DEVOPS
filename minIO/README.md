# MinIO with Docker Compose

This folder deploys a local **MinIO** object storage (S3-compatible) using Docker Compose. It’s ideal for development, demos, and local testing.

> This README is tailored for the `minIO/` directory of this repository. It assumes a standard Compose layout with `docker-compose.yml`, an optional `.env` file for credentials/ports, and a persisted data volume.

---

## Table of Contents
- [What’s included](#whats-included)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Configuration](#configuration)
  - [Environment variables](#environment-variables)
  - [Ports](#ports)
  - [Data volumes](#data-volumes)
- [Using the MinIO Client (mc)](#using-the-minio-client-mc)
- [Create a bucket automatically (optional)](#create-a-bucket-automatically-optional)
- [TLS / HTTPS (optional)](#tls--https-optional)
- [Troubleshooting](#troubleshooting)
- [Clean up](#clean-up)
- [References](#references)

---

## What’s included

A minimal setup to run **single-node** MinIO with:

- **MinIO Server** exposing:
  - S3 API at **:9000**
  - MinIO Console (web UI) at **:9001**
- Optional **MinIO Client (mc)** utility to script bucket/users/policies.

---

## Prerequisites

- Docker Engine **20.10+** / Docker Desktop **4.x+**
- Docker Compose plugin **v2+** (`docker compose version`)

---

## Quick start

From the `minIO/` directory:

```bash
# 0) (Optional) Copy environment defaults
cp -n .env.example .env 2>/dev/null || true

# 1) Set strong root credentials in .env
#    MINIO_ROOT_USER and MINIO_ROOT_PASSWORD are required

# 2) Start MinIO
docker compose up -d

# 3) Open the console
#    Username: MINIO_ROOT_USER
#    Password: MINIO_ROOT_PASSWORD
open http://localhost:9001 || xdg-open http://localhost:9001 || start http://localhost:9001
```

---

## Configuration

### Environment variables

Place these in `.env` (or inline in `docker-compose.yml`):

```ini
# Required
MINIO_ROOT_USER=change-me
MINIO_ROOT_PASSWORD=change-me-too

# Optional (host port mappings)
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001

# Optional data path (host)
MINIO_DATA_PATH=./data
```

- **MINIO_ROOT_USER / MINIO_ROOT_PASSWORD** define the superuser credentials for MinIO. Do **not** use defaults in production.  
- The **console** runs on a separate port; you can pin it via `--console-address :9001` in the server command.

> If you don’t supply credentials, MinIO uses the default `minioadmin/minioadmin` which is not safe beyond local demos.

### Ports

- **9000/tcp** → S3 API (SDK/CLI/clients)
- **9001/tcp** → MinIO Console (web UI)

### Data volumes

- Data persists in a Docker volume or host bind mount (e.g., `${MINIO_DATA_PATH}`) so container restarts don’t lose your objects.

---

## Using the MinIO Client (mc)

The **mc** CLI is convenient for scripting once MinIO is up:

```bash
# Add an alias to your local MinIO
mc alias set local http://localhost:${MINIO_API_PORT:-9000}   "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

# Create a bucket and upload something
mc mb local/my-bucket
mc cp ./README.md local/my-bucket/

# List buckets and objects
mc ls local
mc ls local/my-bucket
```

> You can also run `mc` as a container: `docker run --rm -it --network host minio/mc` and use the same commands.

---

## Create a bucket automatically (optional)

You can add a short-lived **init** service to `docker-compose.yml` that waits for MinIO and creates buckets using `mc`. Example snippet:

```yaml
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":${MINIO_CONSOLE_PORT:-9001}"
    ports:
      - "${MINIO_API_PORT:-9000}:9000"
      - "${MINIO_CONSOLE_PORT:-9001}:9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - ${MINIO_DATA_PATH:-./data}:/data

  createbuckets:
    image: minio/mc:latest
    depends_on:
      - minio
    entrypoint: ["/bin/sh","-c"]
    command: >
      "mc alias set local http://minio:9000 $${MINIO_ROOT_USER} $${MINIO_ROOT_PASSWORD} &&
       mc mb --ignore-existing local/my-bucket &&
       mc anonymous set download local/my-bucket &&
       echo 'Buckets ready.'"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
```

Remove `createbuckets` after the first run if you don’t need it anymore.

---

## TLS / HTTPS (optional)

For local HTTPS you can place certs inside a directory mounted at `/root/.minio/certs/` and run MinIO behind a reverse proxy or expose 443 directly. Example options:

- Use `--certs-dir /root/.minio/certs` and mount your keypair inside the container.
- Or terminate TLS at a proxy (Caddy/Nginx/Traefik) in front of MinIO and keep MinIO on ports 9000/9001.

> When enabling TLS, ensure clients use the correct scheme (`https://`) and update any SDK endpoints accordingly.

---

## Troubleshooting

- **Login fails / default-credentials warning** → Ensure `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` are set and not `minioadmin/minioadmin`.
- **Port already in use** → Change `MINIO_API_PORT`/`MINIO_CONSOLE_PORT` in `.env` or free up ports 9000/9001.
- **“Region is wrong; expecting 'us-east-1'”** → Use the default `us-east-1` for single-node demos or make sure your client region matches server config.
- **Cannot reach console** → Confirm `--console-address` is set and port 9001 is published by Compose.

---

## Clean up

Stop and remove containers (and **data** if you also remove the volume):

```bash
docker compose down
# (Optional, if using a named volume) docker volume rm <volume_name>
```

---

## References

- MinIO root credentials (`MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`).
- MinIO Console and default ports (9000 API, 9001 Console).
- MinIO Client (mc) container image and usage.
- Bucket auto-creation with `mc` in Docker Compose.
