
# Jira Docker Deployment

This directory provides a straightforward setup for deploying Atlassian Jira using Docker. It leverages Docker Compose to simplify the installation and management of Jira in a containerized environment.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Accessing Jira](#accessing-jira)
- [License](#license)

---

## Overview

Atlassian Jira is a popular project management and issue tracking software. Deploying Jira using Docker ensures a consistent and isolated environment, making it easier to manage and scale.

This setup includes:

- A Dockerfile to build the Jira image.
- A `docker-compose.yml` file to define and run the multi-container Docker applications.
- Sample configuration files for customization.

---

## Prerequisites

Before you begin, ensure you have the following installed:

- [Docker](https://www.docker.com/get-started) (version 20.10 or higher)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 1.29 or higher)

---

## Quick Start

1. **Clone the repository:**

   ```bash
   git clone https://github.com/HosseineZolfi/devops-toolkit.git
   cd devops-toolkit/jira-docker
   ```

2. **Build the Jira Docker image:**

   ```bash
   docker-compose build
   ```

3. **Start Jira:**

   ```bash
   docker-compose up -d
   ```

4. **Verify the containers are running:**

   ```bash
   docker-compose ps
   ```

---

## Configuration

- **Jira Home Directory:** By default, Jira stores its data in a volume named `jira-data`. You can customize this by modifying the `docker-compose.yml` file.

- **Ports:** Jira is exposed on port `8080`. If you need to change this, update the `ports` section in the `docker-compose.yml` file.

- **Database:** This setup uses an embedded H2 database for simplicity. For production environments, it's recommended to configure an external database like PostgreSQL or MySQL.

---

## Accessing Jira

Once the containers are up and running, you can access Jira by navigating to:

```
http://localhost:8080
```

Follow the on-screen instructions to complete the Jira setup.

---

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/HosseineZolfi/devops-toolkit/blob/master/LICENSE) file for details.
