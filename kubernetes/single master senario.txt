
# Kubernetes Setup Guide

This guide walks you through the installation and setup process for Kubernetes on a master node. It includes detailed steps for configuring the system, installing necessary tools, and setting up the Kubernetes environment.

## Table of Contents
1. [System Preparation](#1-system-preparation)
2. [Containerd Setup](#2-containerd-setup)
3. [Install Kubernetes](#3-install-kubernetes)
4. [Kubernetes Master Node Setup](#4-kubernetes-master-node-setup)
5. [Auto-Completion for kubectl](#5-auto-completion-for-kubectl)

---

## 1. System Preparation

1. Update and upgrade system packages:
    ```bash
    apt update && sudo apt upgrade -y
    ```

2. Add IP master to `/etc/hosts` and add SNI (like Shecan) to `/etc/resolv.conf`:
    ```bash
    # IP worker
    ```

3. Disable swap:
    ```bash
    swapoff -a
    ```

4. Remove swap entry from `/etc/fstab`:
    ```bash
    sed -i '/swap/d' /etc/fstab
    ```

5. Load the `overlay` module:
    ```bash
    modprobe overlay
    ```

6. Load the `br_netfilter` module:
    ```bash
    modprobe br_netfilter
    ```

7. Load the required modules for Kubernetes:
    ```bash
    tee /etc/modules-load.d/k8s.conf <<EOF
    overlay
    br_netfilter
    EOF
    ```

8. Configure sysctl for Kubernetes networking:
    ```bash
    tee /etc/sysctl.d/k8s.conf <<EOF
    net.bridge.bridge-nf-call-iptables = 1
    net.bridge.bridge-nf-call-ip6tables = 1
    net.ipv4.ip_forward = 1
    EOF
    ```

9. Apply the sysctl settings:
    ```bash
    sysctl --system
    ```

---

## 2. Containerd Setup

1. Install containerd:
    ```bash
    apt install -y containerd
    ```

2. Create a configuration directory for containerd:
    ```bash
    mkdir -p /etc/containerd
    ```

3. Generate the default configuration for containerd:
    ```bash
    containerd config default | tee /etc/containerd/config.toml
    ```

4. Modify containerd's configuration for sandbox image and systemd cgroup:
    ```bash
    sed -i 's|sandbox_image = "registry.k8s.io/pause:3.8"|sandbox_image = "registry.k8s.io/pause:3.9"|' /etc/containerd/config.toml
    sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml
    ```

5. Restart and enable containerd:
    ```bash
    systemctl restart containerd
    systemctl enable containerd
    ```

---

## 3. Install Kubernetes

1. Install necessary dependencies:
    ```bash
    apt-get install -y apt-transport-https ca-certificates curl
    ```

2. Add the Kubernetes APT repository:
    ```bash
    echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /" | tee /etc/apt/sources.list.d/kubernetes.list
    ```

3. Import the Kubernetes GPG key:
    ```bash
    curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
    ```

4. Update APT package index:
    ```bash
    apt update
    ```

5. Check available versions for kubeadm:
    ```bash
    apt list -a kubeadm
    ```

6. Install the required Kubernetes packages:
    ```bash
    apt-get install -y kubeadm=1.30.0-1.1 kubelet=1.30.0-1.1 kubectl=1.30.0-1.1
    ```

7. Enable kubelet service:
    ```bash
    systemctl enable kubelet.service
    ```

8. Hold the packages to prevent automatic updates:
    ```bash
    apt-mark hold kubelet kubeadm kubectl
    ```

---

## 4. Kubernetes Master Node Setup

1. Create the `kubeadm` configuration file `kubeadm-config.yaml`:

    ```yaml
    apiVersion: kubeadm.k8s.io/v1beta3
    kind: InitConfiguration
    nodeRegistration:
      criSocket: "/run/containerd/containerd.sock"

    ---
    apiVersion: kubeadm.k8s.io/v1beta3
    kind: ClusterConfiguration
    kubernetesVersion: "v1.30.0"
    controlPlaneEndpoint: "master:6443"
    imageRepository: "registry.k8s.io"
    networking:
      podSubnet: "10.0.0.0/16"
      serviceSubnet: "10.96.0.0/12"
      dnsDomain: "cluster.local"
    dns:
      imageTag: "v1.10.1"
    ```

2. Run the `kubeadm init` command:
    ```bash
    kubeadm init --config=kubeadm-config.yaml --upload-certs --ignore-preflight-errors=... | tee kubeadm-init.out
    ```

3. Set up the kubeconfig for the user:
    ```bash
    mkdir -p $HOME/.kube
    cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
    chown $(id -u):$(id -g) $HOME/.kube/config
    ```

4. Apply the Calico network plugin:
    ```bash
    wget https://raw.githubusercontent.com/projectcalico/calico/v3.28.2/manifests/calico.yaml
    vim calico.yaml
    # Find the line CALICO_IPV4POOL_CIDR and uncomment it, then replace with:
    #   value: "10.0.0.0/16"
    kubectl apply -f calico.yaml
    ```

---

## 5. Auto-Completion for kubectl

1. Install bash-completion:
    ```bash
    sudo apt install bash-completion -y
    ```

2. Enable kubectl auto-completion:
    ```bash
    echo 'source <(kubectl completion bash)' >> ~/.bashrc
    ```

3. Set up alias and enable alias auto-completion (optional):
    ```bash
    echo 'alias k=kubectl' >> ~/.bashrc
    echo 'complete -o default -F __start_kubectl k' >> ~/.bashrc
    ```

4. Reload the bash configuration:
    ```bash
    source ~/.bashrc
    ```

5. Verify auto-completion:
    ```bash
    echo "✅ Bash completion for kubectl is now enabled! Try using 'kubectl get' and press [TAB] to autocomplete."
    ```

---

End of Kubernetes Setup.
