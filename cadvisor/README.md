
# cAdvisor Deployment Configuration

This directory contains configuration files and scripts for deploying **cAdvisor**, an open-source container monitoring tool developed by Google. cAdvisor provides insights into the resource usage and performance characteristics of running containers.

## Overview

cAdvisor collects, aggregates, processes, and exports information about running containers. It provides an API and a web UI to visualize the collected data, which includes:

- CPU usage
- Memory usage
- Network statistics
- Disk I/O
- File system usage

These metrics are essential for monitoring containerized applications and ensuring optimal performance.

## Directory Structure

The configuration files in this directory are designed to facilitate the deployment of cAdvisor in various environments. The typical structure includes:

- **Dockerfile** *(if present)*: A Dockerfile to build a custom cAdvisor image with your specific configuration and plugins.
- **docker-compose.yml** *(if present)*: A Docker Compose file to define and run multi-container Docker applications, including cAdvisor.

## Getting Started

To deploy cAdvisor using the provided configuration:

1. **Clone the repository:**

   ```bash
   git clone https://github.com/HosseineZolfi/devops-toolkit.git
   cd devops-toolkit/cadvisor
   ```

2. **Review and customize the configuration:**

   - If using Docker, review the `Dockerfile` and `docker-compose.yml` to ensure they meet your requirements.

3. **Deploy using Docker Compose:**

   ```bash
   docker-compose up -d
   ```

   This command will build the Docker image (if necessary) and start the cAdvisor container in detached mode.

4. **Verify the deployment:**

   - Check the status of the cAdvisor container:

     ```bash
     docker ps
     ```

   - Access the cAdvisor web UI by navigating to `http://<your-server-ip>:8080` in your web browser.

## Integrating with Prometheus

To collect metrics from cAdvisor and store them in Prometheus, use the following configuration inside the `prometheus.yml` configuration file:

```yaml
global:
  scrape_interval: 15s  
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
```

This configuration will instruct Prometheus to scrape metrics from cAdvisor every 15 seconds, which can then be visualized using Grafana or analyzed directly from Prometheus.

## Features

- **Real-time monitoring**: View live statistics of container resource usage.
- **Historical data**: Access historical data to analyze trends over time.
- **Metrics export**: Export metrics to monitoring systems like Prometheus.
- **Web UI**: A user-friendly web interface to visualize container metrics.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.
