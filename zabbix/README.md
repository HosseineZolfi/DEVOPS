
# Zabbix Monitoring Setup Guide

This guide walks you through the process of setting up **Zabbix** for server monitoring and configuring the **Zabbix Agent** on target servers for monitoring CPU, memory, disk usage, and more. It also covers setting up alerting rules and custom graphs through the Zabbix frontend.

---

## Prerequisites

- A **Zabbix Server** running (installed using the provided Docker Compose in the Zabbix folder).
- A **Zabbix Agent** to be installed on the target servers that you want to monitor.
- Access to the Zabbix frontend (usually running on port `8080`).

---

## 1) Install Zabbix Agent on Target Servers

To monitor other servers, you need to install the **Zabbix Agent** on the target systems (the systems you wish to monitor).

Run the following commands on the target server to install the Zabbix Agent:

```bash
sudo apt update
sudo apt install zabbix-agent
```

---

## 2) Configure the Zabbix Agent

Once the Zabbix Agent is installed, configure it by editing the `zabbix_agentd.conf` file:

```bash
sudo nano /etc/zabbix/zabbix_agentd.conf
```

Make the following modifications:

- Set the Zabbix server’s IP address in the `Server` and `ServerActive` fields:

  ```ini
  Server=your_zabbix_server_ip
  ServerActive=your_zabbix_server_ip
  ```

- Set the hostname of the target server in the `Hostname` field:

  ```ini
  Hostname=your_server_hostname
  ```

Save the file and exit the editor.

---

## 3) Start and Enable the Zabbix Agent

To start the Zabbix Agent and enable it to run at boot:

```bash
sudo systemctl start zabbix-agent
sudo systemctl enable zabbix-agent
```

---

## 4) Add Hosts to Zabbix Frontend

Once the Zabbix Agent is installed and configured on your servers, you can add those servers as hosts in the Zabbix frontend.

1. Go to **Configuration > Hosts** in the Zabbix frontend.
2. Click **Create Host**.
3. Enter the following details:
   - **Hostname**: Enter the hostname of your server.
   - **IP Address**: Enter the IP address of your target server.
   - **Group**: Assign the appropriate group (e.g., Linux Servers, Web Servers).
4. Under **Agent Interfaces**, configure the **IP address** and **Port** (default Zabbix Agent port `10050`).
5. Click **Save** to finish the configuration.

Once the configuration is saved, Zabbix will start monitoring the host.

---

## 5) Configure Alerting Rules

Zabbix allows you to set up triggers and alerts to notify you when specific thresholds are reached, such as high CPU or memory usage. To configure alerting:

1. Go to **Configuration > Actions**.
2. Create and configure alerting rules:
   - Set up **triggers** for events such as high CPU usage, high memory usage, low disk space, etc.
   - Define the **actions** for sending notifications (e.g., email, Slack, etc.).

---

## 6) Create Custom Graphs

Zabbix lets you create custom graphs to monitor the metrics you care about (e.g., CPU usage, memory usage, disk space). To create custom graphs:

1. Go to **Monitoring > Graphs** in the Zabbix frontend.
2. Click **Create Graph**.
3. Define the metrics to monitor and configure the graph to visualize the desired data.

You can create **custom dashboards** that display key metrics in a visual format to help you track the performance and health of your servers.

---

## Conclusion

By following these steps, you will be able to:

1. Install and configure the **Zabbix Agent** on your target servers.
2. Add your monitored servers as **hosts** in the Zabbix frontend.
3. Configure **alerting rules** to get notified of any critical system events.
4. Create **custom graphs** and **dashboards** to visually monitor system metrics.

Zabbix provides an effective and powerful solution for monitoring your infrastructure and ensuring the health and performance of your servers.

---

### Zabbix Frontend Access:

- URL: `http://your_zabbix_server_ip:8080`
- Default credentials:  
   - Username: `Admin`  
   - Password: `zabbix`
