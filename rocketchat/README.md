# Rocket.Chat with Nginx Reverse Proxy

This repository provides a setup guide for deploying **Rocket.Chat** with **MongoDB** and using **Nginx as a reverse proxy** for better performance and security.

##  Prerequisites
Before starting, ensure that you have the following installed on your server:
- **Docker & Docker Compose**
- **Nginx**
- **Certbot (for SSL - optional)**

##  Project Structure
```
├── docker-compose.yml  # Rocket.Chat and MongoDB setup
├── .env                # Environment variables
├── nginx/
│   ├── rocketchat.conf  # Nginx reverse proxy configuration
```

---

##  Setup Instructions

###  Clone the Repository
```sh
 git clone https://github.com/your-username/rocketchat-nginx.git](https://github.com/HosseineZolfi/DEVOPS.git
 cd rocketchat
```

###  Configure Environment Variables
Edit the `.env` file to set up your domain and database:
```ini
ROOT_URL=http://YOURDOMAIN
MONGODB_VERSION=6.0
MONGODB_DATABASE=rocketchat
MONGODB_REPLICA_SET_NAME=rs0
MONGODB_PORT_NUMBER=27017
ALLOW_EMPTY_PASSWORD=yes
```

### 3 Start Rocket.Chat & MongoDB
```sh
docker compose up -d
```
Verify that the containers are running:
```sh
docker ps
```

### 4 Set Up Nginx as a Reverse Proxy
####  Install Nginx
```sh
sudo apt update && sudo apt install -y nginx
```
####  Configure Nginx
Create the Rocket.Chat configuration file:
```sh
sudo nano /etc/nginx/sites-available/rocketchat
```

Add the following configuration:
```nginx
server {
    listen 80;
    server_name YOURDOMAIN;

    client_max_body_size 100M;

    location / {
        proxy_pass http://localhost:3000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

####  Enable the Configuration & Restart Nginx
```sh
sudo ln -s /etc/nginx/sites-available/rocketchat /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

### 5 Enable HTTPS with Let's Encrypt (Optional)
If you want to enable **SSL**, run:
```sh
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d YOURDOMAIN
```

---

##  How to Deploy Changes
To restart Rocket.Chat after making changes:
```sh
docker compose restart
```
To check logs:
```sh
docker logs -f <rocketchat_container_id>
```

---

##  Troubleshooting
###  413 (Request Entity Too Large) when Uploading Files
Increase the upload size limit in Nginx by setting:
```nginx
client_max_body_size 100M;
```
Then restart Nginx:
```sh
sudo systemctl restart nginx
```

###  WebSocket Issues
Ensure the following headers are set in Nginx:
```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "Upgrade";
```


