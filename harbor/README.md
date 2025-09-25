
# Harbor Setup and Configuration

This guide walks you through setting up Harbor, a cloud-native registry that stores, signs, and scans content, using Docker Compose.

## Table of Contents
- [1. Download and Extract Harbor](#1-download-and-extract-harbor)
- [2. Configure harbor.yml](#2-configure-harboryml)
- [3. Install Docker Compose](#3-install-docker-compose)
- [4. Deploy Harbor Using Docker Compose](#4-deploy-harbor-using-docker-compose)
- [5. Verify Harbor is Running](#5-verify-harbor-is-running)
- [6. Access Harbor Web Interface](#6-access-harbor-web-interface)
- [7. Configure Harbor with Docker Login](#7-configure-harbor-with-docker-login)
- [8. Pushing Images to Harbor](#8-pushing-images-to-harbor)
- [9. Restart & Stop Harbor](#9-restart--stop-harbor)
- [10. Enable HTTPS (Optional)](#10-enable-https-optional)
- [11. Bash Script for Setup](#11-bash-script-for-setup)

---

## 1. Download and Extract Harbor

First, download the latest Harbor installer from the official Harbor GitHub repository:

```bash
curl -LO https://github.com/goharbor/harbor/releases/download/v2.9.0/harbor-online-installer-v2.9.0.tgz
```

Replace `v2.9.0` with the latest version from Harbor Releases.

Extract the archive:

```bash
tar -xvzf harbor-online-installer-v2.9.0.tgz
cd harbor
```

---

## 2. Configure harbor.yml

Copy the default configuration:

```bash
cp harbor.yml.tmpl harbor.yml
```

Edit `harbor.yml`:

```bash
nano harbor.yml
```

Modify these key parameters:

- `hostname: harbor.yourdomain.com` (Change to your domain or IP)
- Configure HTTP (or HTTPS for SSL)
- Set up database settings with a secure password
- Set the admin password

Save and exit (CTRL+X, then Y and ENTER).

---

## 3. Install Docker Compose

Ensure you have Docker Compose installed:

```bash
docker-compose version
```

If not installed, install it:

```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

---

## 4. Deploy Harbor Using Docker Compose

Run the installer:

```bash
sudo ./install.sh
```

Alternatively, you can start Harbor manually:

```bash
docker-compose up -d
```

---

## 5. Verify Harbor is Running

Check running containers:

```bash
docker ps
```

You should see multiple Harbor containers running.

Check logs if there are issues:

```bash
docker-compose logs -f
```

---

## 6. Access Harbor Web Interface

Once Harbor is running, open a browser and go to:

```
http://harbor.yourdomain.com
```

Log in with:

- Username: `admin`
- Password: The password set in `harbor.yml` (default: `Harbor12345`)

---

## 7. Configure Harbor with Docker Login

To use Harbor with Docker, log in to the registry from your CLI:

```bash
docker login harbor.yourdomain.com
```

Enter your admin credentials.

---

## 8. Pushing Images to Harbor

To push an image to Harbor:

1. Tag your image:

```bash
docker tag myimage:latest harbor.yourdomain.com/library/myimage:latest
```

2. Push the image:

```bash
docker push harbor.yourdomain.com/library/myimage:latest
```

---

## 9. Restart & Stop Harbor

To restart Harbor:

```bash
docker-compose restart
```

To stop Harbor:

```bash
docker-compose down
```

---

## 10. Enable HTTPS (Optional)

For SSL/TLS, modify `harbor.yml`:

```yaml
https:
  port: 443
  certificate: /path/to/cert.pem
  private_key: /path/to/private.key
```

Then restart Harbor:

```bash
docker-compose down
docker-compose up -d
```

---

## 11. Bash Script for Setup

Here is a bash script that automates the Harbor installation and setup:

```bash
#!/bin/bash

# Exit immediately if a command fails
set -e

# Variables
HARBOR_VERSION="v2.9.0"
HARBOR_HOSTNAME="harbor.mozlea.ir"
HARBOR_ADMIN_PASSWORD="Harbor12345"
DOCKER_COMPOSE_VERSION="latest"

# Update system packages
echo "Updating system packages..."
sudo apt update -y && sudo apt upgrade -y

# Install dependencies
echo "Installing required dependencies..."
sudo apt install -y curl gnupg2 software-properties-common apt-transport-https ca-certificates

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | bash
    sudo systemctl enable --now docker
else
    echo "Docker is already installed!"
fi

# Add user to Docker group (optional)
sudo usermod -aG docker $USER

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
else
    echo "Docker Compose is already installed!"
fi

# Download and extract Harbor
echo "Downloading Harbor..."
curl -LO https://github.com/goharbor/harbor/releases/download/${HARBOR_VERSION}/harbor-online-installer-${HARBOR_VERSION}.tgz
tar -xvzf harbor-online-installer-${HARBOR_VERSION}.tgz
cd harbor

# Configure Harbor
echo "Configuring Harbor..."
cp harbor.yml.tmpl harbor.yml
sed -i "s/^hostname:.*/hostname: ${HARBOR_HOSTNAME}/" harbor.yml
sed -i "s/^harbor_admin_password:.*/harbor_admin_password: ${HARBOR_ADMIN_PASSWORD}/" harbor.yml

# Install Harbor
echo "Installing Harbor..."
sudo ./install.sh

# Start Harbor using Docker Compose
echo "Starting Harbor..."
docker-compose up -d

# Verify installation
echo "Checking Harbor status..."
docker ps | grep harbor

# Output success message
echo "✅ Harbor is successfully installed and running on https://${HARBOR_HOSTNAME}!"
```

---

Harbor is Now Ready! 🚀

You have successfully deployed Harbor using Docker Compose. You can now use it as a private container registry.

Let me know if you need further assistance! 🚀
