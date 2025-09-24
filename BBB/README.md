# BigBlueButton Deployment

This repository provides a comprehensive setup for deploying BigBlueButton (BBB), an open-source web conferencing system tailored for online learning. It includes configurations and scripts to facilitate the installation and management of BBB on a dedicated server.

## Overview

BigBlueButton is designed to support real-time sharing of audio, video, slides (with whiteboard annotations), chat, and screen. It offers features such as:

- **Multi-user whiteboard**: Collaborate in real-time on a shared whiteboard.
- **Breakout rooms**: Divide participants into smaller groups for focused discussions.
- **Polling**: Engage participants with real-time polls.
- **Chat**: Communicate via public and private chat.
- **Document upload**: Share presentations and documents.
- **Shared notes**: Collaborate on shared notes during sessions.
- **Screen sharing**: Present your screen to participants.
- **Webcam video**: Share live video feeds.
- **Learning Analytics Dashboard**: Monitor participant engagement and learning metrics.

For a detailed list of features, refer to the official BigBlueButton features page ([bigbluebutton.org](https://bigbluebutton.org/features/?utm_source=chatgpt.com)).

## Prerequisites

Before deploying BigBlueButton, ensure your server meets the following requirements:

- **Operating System**: Ubuntu 20.04 64-bit
- **CPU**: Minimum 4 cores
- **RAM**: Minimum 8 GB
- **Storage**: At least 50 GB of free space
- **Bandwidth**: 1 Gbps recommended

For detailed installation instructions, refer to the official BigBlueButton installation guide ([bigbluebutton.github.io](https://bigbluebutton.github.io/2.5/install.html?utm_source=chatgpt.com)).

## Deployment

This repository includes scripts and configurations to automate the deployment of BigBlueButton. To get started:

1. Clone this repository to your server:

   ```bash
   git clone https://github.com/HosseineZolfi/DEVOPS.git
   cd DEVOPS/BBB
