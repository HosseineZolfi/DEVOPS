# WireGuard VPN Setup Guide

This README explains how to set up **WireGuard** on an **Ubuntu client** and configure a WireGuard server using Docker. 

### Prerequisites

- **Ubuntu client** system for installation
- **WireGuard Docker server** running (configured using the provided `docker-compose.yml`)

---

## 1) Client Setup on Ubuntu

### Install WireGuard

To install WireGuard on your Ubuntu client, run:

```bash
sudo apt update
sudo apt install wireguard
```

### Generate Keys

Generate a private and public key pair for the client:

```bash
wg genkey | tee privatekey | wg pubkey > publickey
```

> This will create two files: `privatekey` (client's private key) and `publickey` (client's public key).

---

## 2) Configure WireGuard on the Client

Create the WireGuard configuration file `wg0.conf`:

```bash
sudo vi /etc/wireguard/wg0.conf
```

Add the following content to `wg0.conf`, replacing the placeholder values with your actual keys and server details:

```ini
[Interface]
Address = 10.0.0.2/24
PrivateKey = <client-private-key>

[Peer]
PublicKey = <server-public-key>
Endpoint = <server-ip>:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
```

- `<client-private-key>`: Replace this with the **client’s private key** generated earlier.
- `<server-public-key>`: Replace this with the **server’s public key**.
- `<server-ip>`: Replace with the **server’s public IP** or DNS.

---

## 3) Connect to WireGuard VPN

Once your `wg0.conf` is set up, you can start the VPN connection:

```bash
sudo wg-quick up wg0
```

To verify the connection:

```bash
sudo wg show
```

---

## 4) Disconnect from the VPN

To disconnect the VPN, run:

```bash
sudo wg-quick down wg0
```

---

## Docker Configuration for WireGuard Server

### `docker-compose.yml`

Below is a **Docker Compose configuration** for deploying WireGuard in a Docker container, along with **WireGuard-UI** for managing the VPN.

```yaml
version: "3"

services:

  # WireGuard VPN service
  wireguard:
    image: linuxserver/wireguard:1.0.20210914-r4-ls39
    container_name: wireguard
    cap_add:
      - NET_ADMIN
    volumes:
      - ./config:/config
    ports:
      # Port for WireGuard-UI
      # Port of the WireGuard VPN server
      - "51820:51820/udp"
    networks:
      - wg-net

  # WireGuard-UI service
  wireguard-ui:
    image: ngoduykhanh/wireguard-ui:0.6.1
    container_name: wireguard-ui
    ports:
      - "5000:5000"
    depends_on:
      - wireguard
    cap_add:
      - NET_ADMIN
    environment:
      - SENDGRID_API_KEY
      - EMAIL_FROM_ADDRESS
      - EMAIL_FROM_NAME
      - SESSION_SECRET
      - WGUI_USERNAME=admin
      - WGUI_PASSWORD=password
      - WG_CONF_TEMPLATE
      - WGUI_MANAGE_START=true
      - WGUI_MANAGE_RESTART=true
    logging:
      driver: json-file
      options:
        max-size: 50m
    volumes:
      - ./db:/app/db
      - ./config:/etc/wireguard
    networks:
      - wg-net

networks:
  wg-net:
```

### Key Notes

- **WireGuard Service**: This service creates a VPN endpoint exposed on port `51820/udp`. It uses the `linuxserver/wireguard` image.
- **WireGuard-UI Service**: This provides a web-based UI for managing the WireGuard server, accessible on port `5000`. Configuration data is stored in `./config` and `./db`.
- **Networking**: Both services are connected to the custom network `wg-net`, which allows the WireGuard UI to interact with the WireGuard service.

---

## 5) Start the Docker Compose Stack

Once the configuration is in place, you can start the services:

```bash
docker-compose up -d
```

This will start both **WireGuard** and **WireGuard-UI** services.

---

## 6) Access the WireGuard-UI

Navigate to `http://<your-docker-host-ip>:5000` to access the **WireGuard-UI**. Log in using the default credentials:

- **Username**: `admin`
- **Password**: `password`

---

## Summary

1. Install WireGuard on your Ubuntu client.
2. Generate client keys and configure `wg0.conf`.
3. Start the VPN connection using `wg-quick`.
4. Set up WireGuard in Docker using `docker-compose.yml`.
5. Access the WireGuard-UI for management.

With this setup, you should now be able to easily manage and connect to your WireGuard VPN through Docker.

---
