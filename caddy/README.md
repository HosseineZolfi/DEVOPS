
# Caddy Deployment Configuration

This directory contains configuration files and scripts for deploying **Caddy**, a modern, general-purpose web server with automatic HTTPS capabilities. Caddy is known for its simplicity, security, and performance, making it an excellent choice for both development and production environments.

## Overview

Caddy automatically provisions and renews SSL/TLS certificates using Let's Encrypt, providing secure connections out of the box. It supports reverse proxying, static file serving, and can be extended with plugins for additional functionality.

## Directory Structure

The configuration files in this directory are designed to facilitate the deployment of Caddy in various environments. The typical structure includes:

- **Caddyfile**: The main configuration file for Caddy, defining how it serves your site(s).
- **Dockerfile** *(if present)*: A Dockerfile to build a custom Caddy image with your specific configuration and plugins.
- **docker-compose.yml** *(if present)*: A Docker Compose file to define and run multi-container Docker applications, including Caddy.

## Getting Started

To deploy Caddy using the provided configuration:

1. **Clone the repository:**

   ```bash
   git clone https://github.com/HosseineZolfi/devops-toolkit.git
   cd devops-toolkit/caddy
   ```

2. **Review and customize the configuration:**

   - Open the `Caddyfile` and adjust the server blocks to match your domain names and desired settings.
   - If using Docker, review the `Dockerfile` and `docker-compose.yml` to ensure they meet your requirements.

3. **Deploy using Docker Compose:**

   ```bash
   docker-compose up -d
   ```

   This command will build the Docker image (if necessary) and start the Caddy container in detached mode.

4. **Verify the deployment:**

   - Check the status of the Caddy container:

     ```bash
     docker ps
     ```

   - Access your domain in a web browser to ensure Caddy is serving your site correctly.

## Features

- **Automatic HTTPS**: Caddy automatically obtains and renews SSL/TLS certificates for your sites.
- **Reverse Proxying**: Easily configure Caddy to proxy requests to backend services.
- **Static File Serving**: Serve static files with efficient handling of MIME types and caching.
- **Extensibility**: Extend Caddy's functionality with a wide range of plugins.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.
