
# Ansible Setup on Ubuntu 22.04 Using Python Environment (Virtualenv) and pip

This guide walks you through the process of setting up an Ansible server on **Ubuntu 22.04** using a **Python virtual environment** and `pip`. 

## Prerequisites

Before you start, make sure you have the following:

- Ubuntu 22.04 server (or desktop)
- A non-root user with sudo privileges

## Step-by-Step Guide

### 1. Install Required System Packages

First, update your package list and install the required system dependencies:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 2. Create a Dedicated User (optional but recommended)

It’s a good idea to create a separate user for Ansible:

```bash
sudo adduser ansible
sudo usermod -aG sudo ansible
su - ansible
```

### 3. Set Up a Python Virtual Environment

Navigate to your desired directory and create a Python virtual environment:

```bash
mkdir ~/ansible_env && cd ~/ansible_env
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your prompt, indicating that the virtual environment is activated.

### 4. Install Ansible Using pip

With the virtual environment active, install Ansible:

```bash
pip install --upgrade pip
pip install ansible
```

Check if Ansible was installed successfully:

```bash
ansible --version
```

### 5. Create an Inventory and Basic Config (Optional but Useful)

You can create an inventory file and a basic configuration file:

```bash
mkdir inventory
echo -e "[local]
localhost ansible_connection=local" > inventory/hosts
```

For basic configuration:

```bash
echo -e "[defaults]
inventory = ./inventory/hosts
host_key_checking = False" > ansible.cfg
```

### 6. Test Ansible

Test if Ansible is working correctly:

```bash
ansible all -m ping
```

You should see:

```
localhost | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

### 7. Optional: Install Extra Collections or Modules

You can install extra collections or modules like:

```bash
ansible-galaxy collection install community.general
```

## Notes

- Always activate the virtual environment by running `source venv/bin/activate` before using Ansible.
- To deactivate the virtual environment, simply run `deactivate`.

## Conclusion

You now have a clean, isolated Ansible setup using a Python virtual environment. This allows you to manage your configurations and playbooks without interfering with system-wide Python packages.
