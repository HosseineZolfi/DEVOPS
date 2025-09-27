# Monitoring Stack (Docker Compose)

This folder contains a Docker Compose–based **observability stack** for local or small‑scale environments. It typically includes:

- **Prometheus** – metrics collection & time‑series DB
- **Node Exporter** – host metrics
- **cAdvisor** – container metrics
- **Alertmanager** – alert routing/notification
- **Grafana** – dashboards & alerting UI
- *(optional)* **Loki + Promtail** – log aggregation

> This README is tailored for the `monitoring-stack/` directory of this repo. If your folder contents differ, keep the flow and adjust service names/paths to match your files.

---

## Table of Contents
- What's inside
- Prerequisites
- Quick start
- Configuration
  - Environment (.env)
  - Prometheus config
  - Alertmanager config
  - Grafana provisioning
  - Loki & Promtail (optional)
- Ports
- Data volumes
- Dashboards
- Health checks & verification
- Troubleshooting
- Clean up
- Notes for production

---

## What's inside

Expected file layout (yours may vary):

```
monitoring-stack/
├─ docker-compose.yml
├─ .env.example
├─ prometheus/
│  ├─ prometheus.yml
│  └─ alerts/
├─ alertmanager/
│  └─ alertmanager.yml
├─ grafana/
│  ├─ provisioning/
│  │  ├─ datasources/
│  │  └─ dashboards/
│  └─ dashboards/
├─ loki/
│  └─ loki-config.yml
└─ promtail/
   └─ promtail-config.yml
```

---

## Prerequisites

- Docker Engine 20.10+ / Docker Desktop 4.x+
- Docker Compose v2+
- ~2–4 GB RAM free

---

## Quick start

```bash
cp -n .env.example .env 2>/dev/null || true
docker compose up -d
docker compose ps
```

Open UIs:
- Grafana → http://localhost:3000 (default `admin` / password from `.env` or Grafana default)
- Prometheus → http://localhost:9090
- Alertmanager → http://localhost:9093
- Node Exporter → http://localhost:9100/metrics
- cAdvisor → http://localhost:8080
- Loki → http://localhost:3100 (if enabled)

---

## Configuration

### Environment (.env)

```ini
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=change-me

PROMETHEUS_PORT=9090
ALERTMANAGER_PORT=9093
GRAFANA_PORT=3000
NODE_EXPORTER_PORT=9100
CADVISOR_PORT=8080
LOKI_PORT=3100

PROMETHEUS_STORAGE=./prometheus-data
GRAFANA_STORAGE=./grafana-data
LOKI_STORAGE=./loki-data
```

### Prometheus config

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs: [{ targets: ['prometheus:9090'] }]
  - job_name: 'node-exporter'
    static_configs: [{ targets: ['node-exporter:9100'] }]
  - job_name: 'cadvisor'
    static_configs: [{ targets: ['cadvisor:8080'] }]

rule_files:
  - "alerts/*.yml"
```

### Alertmanager config

```yaml
route:
  receiver: 'default'
receivers:
  - name: 'default'
    # email_configs:
    # slack_configs:
```

### Grafana provisioning

**Datasource (prometheus.yml):**
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

**Dashboards provider:**
```yaml
apiVersion: 1
providers:
  - name: 'local-dashboards'
    type: file
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: true
```

### Loki & Promtail (optional)

**promtail-config.yml (minimal):**
```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: containers
    static_configs:
      - targets: [localhost]
        labels:
          job: varlogs
          __path__: /var/log/*.log
```

---

## Ports

| Service | Port |
| --- | --- |
| Grafana | 3000 |
| Prometheus | 9090 |
| Alertmanager | 9093 |
| Node Exporter | 9100 |
| cAdvisor | 8080 |
| Loki | 3100 |

---

## Data volumes

Use persistent volumes for Prometheus and Grafana to preserve data between restarts.

---

## Dashboards

Import popular dashboards (e.g., Node Exporter Full – ID 1860) or place JSON files in `grafana/dashboards/` and provision them.

---

## Health checks & verification

- Prometheus **Status → Targets** should show **UP** targets.
- Try queries like `up`, `node_load1`, `container_memory_usage_bytes`.
- Build a simple Grafana panel to verify data flow.

---

## Troubleshooting

- Targets DOWN → check service names/ports in `prometheus.yml`.
- Grafana cannot reach Prometheus → confirm datasource URL and network.
- Volume permissions → match container user IDs (Grafana UID 472).
- Port conflicts → change host mappings in compose/.env.

---

## Clean up

```bash
docker compose down
# or to remove data too:
docker compose down -v
```

---

## Notes for production

- Consider Thanos/Cortex/Mimir for long-term metrics.
- Protect UIs with auth + TLS (reverse proxy).
- Pin image versions; size retention & resources appropriately.
