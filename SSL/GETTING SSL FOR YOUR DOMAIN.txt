
# SSL Certificate Setup for Nginx with Certbot

This guide walks you through the steps to install SSL certificates for your domain using **Certbot** with **Nginx**. Certbot is an easy-to-use tool that automates the process of obtaining and renewing SSL certificates from **Let's Encrypt**, a free Certificate Authority.

## Prerequisites

Before you begin, make sure you have:

- A server running **Ubuntu** or another **Debian-based** Linux distribution.
- **Nginx** installed and configured.
- A **domain** that points to your server's public IP.
- Access to the server with **sudo** privileges.

## Steps to Install SSL with Nginx and Certbot

### 1. Install Nginx, Certbot, and Certbot Nginx Plugin

First, install **Nginx**, **Certbot**, and the Certbot Nginx plugin to manage SSL certificates.

```bash
sudo apt install nginx certbot python3-certbot-nginx
```

### 2. Configure Nginx Server Block

Next, configure Nginx to proxy requests to your web application. Open the Nginx configuration file for your domain:

```bash
sudo vi /etc/nginx/sites-available/yourdomain.com
```

Add the following configuration to the file, replacing `your_domain.com` with your actual domain name and adjust the proxy settings if needed.

```nginx
server {
    listen 80;

    server_name your_domain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Enable the Site Configuration

Create a symbolic link to enable the site configuration:

```bash
sudo ln -s /etc/nginx/sites-available/yourdomain.com /etc/nginx/sites-enabled
```

### 4. Test Nginx Configuration

Test your Nginx configuration to ensure there are no syntax errors:

```bash
sudo nginx -t
```

If the test is successful, proceed to reload Nginx.

### 5. Reload Nginx

Reload Nginx to apply the changes:

```bash
sudo systemctl reload nginx
```

### 6. Obtain SSL Certificate Using Certbot

Now, use Certbot to automatically obtain and configure an SSL certificate for your domain with Nginx:

```bash
sudo certbot --nginx -d your_domain.com
```

Certbot will handle the process of obtaining the SSL certificate and configuring Nginx to use it.

### 7. Verify SSL Certificate Renewal

Once the SSL certificate is installed, you can test the renewal process using the `--dry-run` option:

```bash
sudo certbot renew --dry-run
```

This ensures that Certbot will automatically renew your SSL certificate when necessary.

### 8. Check Certbot Timer

Verify that Certbot is configured to automatically renew your SSL certificates by checking the status of the **certbot.timer** service:

```bash
sudo systemctl status certbot.timer
```

This service will handle automatic renewal of your certificates when the expiration date approaches.

## Conclusion

You have successfully set up SSL for your domain using **Certbot** and **Nginx**. Your site is now secured with an SSL certificate from **Let's Encrypt**.

### Additional Resources

- [Certbot Documentation](https://certbot.eff.org/docs/)
- [Nginx Documentation](https://nginx.org/en/docs/)
