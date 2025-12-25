# Pi-Experiments

A collection of progressively sophisticated applications for Raspberry Pi 5, focusing on resource-efficient terminal and desktop applications.

## About

This repository documents my journey learning Linux system development on a Raspberry Pi 5. Coming from a background in terminal applications and Electron apps (Mac/Windows), this project explores what's possible on a resource-constrained Linux device.

### Background
- **Experience**: Terminal applications, Electron desktop apps (Mac/Windows)
- **Learning**: Linux system development and optimization
- **Goal**: Build progressively complex applications that leverage the Pi's capabilities

## Project Ideas

### 1. **System Monitor Dashboard**
A terminal-based system monitor showing CPU, memory, temperature, and network stats in real-time. Perfect first project to learn Linux system APIs and terminal UI libraries.
Implemented at `system_monitor_dashboard/`.

### 11. **World Status Dashboard**
At-a-glance terminal dashboard with date/time, local weather, and news summary.
Implemented at `world_status_dashboard/`.

### 2. **Home Weather Station**
Collect and display weather data from connected sensors. Web interface for viewing historical data and current conditions. Introduces sensor integration and data visualization.

### 3. **Network-Wide Ad Blocker (Pi-hole Alternative)**
DNS-based ad blocking for your entire network. Learn about DNS, networking, and building system services that run in the background.

### 4. **Personal Media Server**
Stream music and videos to devices on your network. Explore file systems, media transcoding, and building efficient streaming protocols.

### 5. **Smart Home Hub**
Control IoT devices, create automation rules, and build a web interface for management. Bridges multiple protocols (MQTT, Zigbee, HTTP) into one system.

### 6. **Local AI Assistant**
Run lightweight AI models locally for voice commands, text processing, or image recognition. Learn about edge AI and optimizing models for ARM architecture.

### 7. **Git Repository Mirror & CI/CD Server**
Automated build and test pipeline for your projects. Host git repos locally and run builds on commit. Great for learning DevOps concepts.

### 8. **VPN Gateway with Traffic Analytics**
Route traffic through VPN, monitor bandwidth usage, and visualize network patterns. Deep dive into networking, security, and data visualization.

### 9. **Distributed Task Queue Manager**
Build a job scheduling system that can distribute work across multiple Pis. Learn about distributed systems, message queues, and cluster computing.

### 10. **Retro Gaming Station with Cloud Save**
Emulation platform with automatic save state sync to cloud storage. Combines entertainment with learning about emulation, file sync, and building polished UIs.

## Development Environment

Project is running on:
- Raspberry Pi 5
- Linux environment

## License

MIT
