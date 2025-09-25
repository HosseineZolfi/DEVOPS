
# GitLab Setup and Configuration

This directory contains configurations and setup files for integrating GitLab with various DevOps practices, including CI/CD pipelines, GitLab runners, and configuration for managing GitLab with Docker. This README provides an overview of how to get started, configuration details, and common tasks to manage GitLab effectively in your development environment.

---

## Table of contents
- [What you get](#what-you-get)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
  - [GitLab CI/CD Setup](#gitlab-cicd-setup)
  - [GitLab Runner](#gitlab-runner)
  - [Docker Integration](#docker-integration)
- [Common Tasks](#common-tasks)
  - [Create a New Pipeline](#create-a-new-pipeline)
  - [Trigger a Job](#trigger-a-job)
  - [Manage CI/CD Variables](#manage-cicd-variables)
- [Troubleshooting](#troubleshooting)
- [Clean Up](#clean-up)
- [Notes for Production](#notes-for-production)
- [Credits](#credits)

---

## What you get

This repository provides a full GitLab setup for DevOps workflows:

- **GitLab**: Version control and repository management.
- **GitLab CI/CD Pipelines**: Configuration to automate testing, building, and deployment processes.
- **GitLab Runner**: Configuration for executing pipeline jobs on your own infrastructure.

This setup also includes Docker integration to run GitLab services in isolated containers.

---

## Prerequisites

Before setting up GitLab with Docker, ensure you have the following installed:

- Docker Engine **20.10+** / Docker Desktop **4.x+**
- Docker Compose plugin **v2+** (`docker compose version`)
- GitLab account and access to a repository
- Basic understanding of CI/CD pipelines

---

## Quick Start

1. **Clone the repository** and navigate to the `gitlab/` folder.

```bash
# Clone the repository
git clone https://github.com/HosseineZolfi/devops-toolkit.git
cd devops-toolkit/gitlab
```

2. **Start GitLab with Docker Compose**:

```bash
# Run the GitLab services in the foreground
docker compose up
```

Alternatively, you can run it in detached mode:

```bash
docker compose up -d
```

3. **Access GitLab** at `http://localhost:8080` (default). Log in with the default admin credentials (provided by your Docker setup or `.env` file).

> **Important**: Make sure to change the default password after logging in.

---

## Configuration

### GitLab CI/CD Setup

GitLab CI/CD pipelines are configured using the `.gitlab-ci.yml` file. This file defines the stages, jobs, and scripts for automating the process of continuous integration and delivery.

Example `.gitlab-ci.yml`:

```yaml
stages:
  - build
  - test
  - deploy

build_job:
  stage: build
  script:
    - echo 'Building project'

test_job:
  stage: test
  script:
    - echo 'Running tests'

deploy_job:
  stage: deploy
  script:
    - echo 'Deploying project'
```

### GitLab Runner

GitLab Runner is an application used to run your CI/CD jobs. It’s integrated with GitLab and can be configured to run locally or in the cloud.

To register a GitLab Runner with your GitLab instance, use the following command:

```bash
gitlab-runner register
```

You will need to provide your GitLab instance URL and a registration token. This process links your runner to the GitLab instance and allows it to execute jobs from the CI/CD pipeline.

### Docker Integration

GitLab can be run inside Docker containers using `docker-compose`. You can use this setup to create isolated environments for your GitLab services, including GitLab itself, the GitLab Runner, and associated dependencies.

Sample Docker Compose file `docker-compose.yml`:

```yaml
version: '3.8'

services:
  gitlab:
    image: gitlab/gitlab-ce:latest
    ports:
      - '8080:8080'
      - '22:22'
    volumes:
      - 'gitlab-config:/etc/gitlab'
      - 'gitlab-logs:/var/log/gitlab'
      - 'gitlab-data:/var/opt/gitlab'

volumes:
  gitlab-config:
  gitlab-logs:
  gitlab-data:
```

---

## Common Tasks

### Create a New Pipeline

1. Make changes in your repository and push the changes to GitLab.
2. GitLab automatically triggers a pipeline based on the configuration in `.gitlab-ci.yml`.
3. You can view the progress and status of your pipeline in the GitLab web interface.

### Trigger a Job

You can manually trigger jobs in a pipeline from the GitLab interface or using the GitLab API.

### Manage CI/CD Variables

GitLab allows you to define variables for use in your pipeline scripts, which can be managed in the **Settings > CI / CD** section of your GitLab project.

---

## Troubleshooting

- **GitLab not starting**: Check Docker logs (`docker compose logs`) and ensure all required ports are open and not blocked.
- **Pipeline failures**: Inspect pipeline logs in the GitLab UI to identify the error details.
- **Docker-related errors**: Ensure your Docker environment is set up correctly with enough resources (memory and CPU) for the GitLab containers.

---

## Clean Up

To stop and remove the GitLab containers and volumes:

```bash
docker compose down -v
```

This will also remove the associated data volumes, cleaning up your local environment.

---

## Notes for Production

For a production environment:

- Use a dedicated server with sufficient resources for GitLab and GitLab Runner.
- Set up proper backups for GitLab data and configuration.
- Secure your GitLab instance using SSL/TLS, configure firewalls, and apply necessary security patches.

---

## Credits

This repository follows GitLab's official documentation for setting up and managing GitLab services using Docker. You can find further details in the [official GitLab documentation](https://docs.gitlab.com/).
