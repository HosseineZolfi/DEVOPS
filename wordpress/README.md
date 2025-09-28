# WordPress & MySQL Docker Setup Guide

This guide helps you configure and deploy a **WordPress** application with a **MySQL** database using Docker Compose. The setup is configured using environment variables stored in an `.env` file for ease of customization.

---

## Prerequisites

- Docker and Docker Compose installed on your system.
- Basic knowledge of Docker and Docker Compose.
- A running environment to deploy the containers (local or cloud-based).

---

## Environment Configuration

To securely configure your WordPress and MySQL containers, create a `.env` file in your project directory with the following environment variables:

```ini
MYSQL_ROOT_PASSWORD=yourpassword
MYSQL_DATABASE=wordpress
MYSQL_USER=youruser
MYSQL_PASSWORD=yourpassword
WORDPRESS_DB_HOST=db:3306
WORDPRESS_DB_USER=youruser
WORDPRESS_DB_PASSWORD=yourpassword
WORDPRESS_DB_NAME=wordpress
```

- **MYSQL_ROOT_PASSWORD**: The root password for MySQL.
- **MYSQL_DATABASE**: The name of the database to create for WordPress.
- **MYSQL_USER**: The MySQL user to access the database.
- **MYSQL_PASSWORD**: The password for the `MYSQL_USER`.
- **WORDPRESS_DB_HOST**: The MySQL host (use the service name `db` defined in Docker Compose).
- **WORDPRESS_DB_USER**: The WordPress database user.
- **WORDPRESS_DB_PASSWORD**: The password for the WordPress database user.
- **WORDPRESS_DB_NAME**: The database name that WordPress will use.

---

## Docker Compose Configuration

This configuration deploys **MySQL** as the database and **WordPress** as the web application. Both services will be linked in a custom Docker network for communication.

### `docker-compose.yml`

```yaml
version: "3.8"

services:
  # MySQL service
  db:
    image: mysql:5.7
    container_name: mysql_db
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - db_data:/var/lib/mysql
    networks:
      - wordpress_network
    env_file:
      - .env

  # WordPress service
  wordpress:
    image: wordpress:latest
    container_name: wordpress_app
    restart: always
    environment:
      WORDPRESS_DB_HOST: ${WORDPRESS_DB_HOST}
      WORDPRESS_DB_USER: ${WORDPRESS_DB_USER}
      WORDPRESS_DB_PASSWORD: ${WORDPRESS_DB_PASSWORD}
      WORDPRESS_DB_NAME: ${WORDPRESS_DB_NAME}
    volumes:
      - wordpress_data:/var/www/html
    ports:
      - "8080:80"
    depends_on:
      - db
    networks:
      - wordpress_network
    env_file:
      - .env

volumes:
  db_data:
  wordpress_data:

networks:
  wordpress_network:
```

### Key Configuration

- **`db` (MySQL Service)**:
  - Uses the **mysql:5.7** Docker image.
  - Environment variables configured from the `.env` file.
  - Data persists in a Docker volume (`db_data`) to maintain state across container restarts.
  - Exposes MySQL on the internal network at port `3306`.

- **`wordpress` (WordPress Service)**:
  - Uses the latest **wordpress:latest** Docker image.
  - Configured to connect to the MySQL service using the environment variables from the `.env` file.
  - Exposes WordPress on **port `8080`** to allow access via `http://localhost:8080`.
  - Depends on the `db` service, ensuring MySQL starts before WordPress.

- **Volumes**:
  - `db_data`: Holds MySQL data.
  - `wordpress_data`: Holds WordPress files.

- **Networks**:
  - `wordpress_network`: Custom network allowing both services to communicate securely.

---

## Deploying the Stack

To deploy the WordPress and MySQL containers, follow these steps:

1. Create the `.env` file with your configuration values (see section above).
2. Run the following command to start the services:

   ```bash
   docker-compose up -d
   ```

3. This will pull the necessary Docker images and start the containers in the background.

---

## Access WordPress

After the containers are up and running, you can access your WordPress application at:

```bash
http://localhost:8080
```

The WordPress installation page will appear, and you can proceed with the installation by following the prompts.

---

## Stopping and Cleaning Up

To stop and remove the running containers, use the following command:

```bash
docker-compose down
```

To remove the containers along with the volumes (which will delete the data), run:

```bash
docker-compose down -v
```

---

## Summary

- Set up environment variables in the `.env` file.
- Configure WordPress and MySQL using Docker Compose.
- Deploy the containers with `docker-compose up -d`.
- Access WordPress at `http://localhost:8080` for setup.

With this setup, you now have a fully functional WordPress site running with MySQL using Docker.

---
