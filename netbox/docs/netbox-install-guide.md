# NetBox 4.x Homelab Deployment Guide

**Version:** NetBox 4.5.4 | Docker Compose  
**Target:** Proxmox VE homelab on Ubuntu 24.04 LTS  
**Author:** SG | March 2026

---

## What is NetBox?

NetBox is an open-source **Infrastructure Resource Modeling (IRM)** tool — essentially a source of truth for your network and infrastructure. Think of it as a CMDB (Configuration Management Database) that engineers actually want to use.

It tracks:
- **Physical devices** — servers, switches, NAS, routers
- **Virtual machines** — with resource specs and host assignments
- **IP addresses** — full IPAM (IP Address Management)
- **Network prefixes** — subnets, VLANs, routing
- **Everything connected** — cables, interfaces, power

The key differentiator: NetBox has a powerful REST API, which means everything you enter can be read by Ansible, Terraform, and other automation tools. Your documentation becomes your infrastructure.

---

## Architecture Decisions

Before deploying, several key decisions were made:

**Docker Compose over native install** — easier upgrades, all dependencies containerized, single command to start/stop.

**Dedicated VM on underutilized node** — deployed on HP DL360 (14% RAM utilization) rather than the primary workload node.

**Dedicated PostgreSQL in Docker stack** — not sharing the existing PostgreSQL VM, keeping NetBox self-contained.

**Internal domain: netbox.qnet.local** — consistent with internal DNS naming convention.

---

## Phase 1 — VM Creation in Proxmox

### Specifications

| Setting | Value |
|---------|-------|
| VM ID | 720 |
| Name | netbox |
| Node | pve (HP DL360, 192.168.9.80) |
| OS | Ubuntu 24.04.1 LTS |
| CPU | 2 cores, host type |
| RAM | 4096 MiB |
| Disk | 40GB, local-lvm, raw format |
| BIOS | OVMF (UEFI) |
| Machine | q35 |
| Network | virtio, vmbr0 |
| IP | 192.168.9.150/24 (static) |

### Static IP Configuration (netplan)

```yaml
# /etc/netplan/50-cloud-init.yaml
network:
  version: 2
  ethernets:
    ens18:
      addresses:
        - 192.168.9.150/24
      routes:
        - to: default
          via: 192.168.9.1
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
```

```bash
sudo netplan apply
```

**Important:** Also create a DHCP reservation in your router matching the VM's MAC address to prevent IP conflicts.

### Disk Expansion Fix

Ubuntu 24.04 only uses ~18GB of a 40GB disk by default. Expand the logical volume:

```bash
sudo lvextend -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
sudo resize2fs /dev/ubuntu-vg/ubuntu-lv
df -h /  # verify
```

---

## Phase 2 — System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essentials
sudo apt install -y curl wget git ufw qemu-guest-agent

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Enable guest agent (allows Proxmox to see VM IP)
sudo systemctl enable qemu-guest-agent
sudo systemctl start qemu-guest-agent
```

---

## Phase 3 — Docker Installation

```bash
# Add Docker's official GPG key
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER

# Verify
docker --version
```

Log out and back in for group membership to take effect.

---

## Phase 4 — NetBox Deployment

### Clone and Configure

```bash
sudo git clone -b release \
  https://github.com/netbox-community/netbox-docker.git \
  /opt/netbox-docker
sudo chown -R $USER:$USER /opt/netbox-docker
cd /opt/netbox-docker
```

### Port Override

```bash
cat << 'EOF' > docker-compose.override.yml
services:
  netbox:
    ports:
      - "8000:8080"
EOF
```

### Environment Configuration

Edit `/opt/netbox-docker/env/netbox.env`:

```bash
SKIP_SUPERUSER=false
SUPERUSER_NAME=admin
SUPERUSER_EMAIL=admin@netbox.local
SUPERUSER_PASSWORD=<your-secure-password>
```

Edit `/opt/netbox-docker/env/postgres.env`:
```bash
POSTGRES_PASSWORD=<your-db-password>
```

### Start the Stack

```bash
cd /opt/netbox-docker
docker compose up -d
docker compose ps  # verify all containers are healthy
```

All containers should show `healthy` status:
- `netbox` — main application
- `netbox-worker` — background job processor
- `postgres` — database
- `redis` — cache
- `redis-cache` — additional cache

Access at: `http://<VM-IP>:8000`

### Important: NetBox 4.x API Token Format

NetBox 4.x uses **v2 tokens** in the format:
```
nbt_<KEY>.<SECRET>
```

The full token is only shown **once** at creation time. The "Example Usage" on the token detail page shows the correct format:
```bash
curl -X GET \
  -H "Authorization: Bearer nbt_<KEY>.<SECRET>" \
  https://your-netbox/api/status/
```

When using `pynetbox` library, pass the full token string including the `nbt_` prefix.

---

## Phase 5 — Auto-Start Configuration

Create a systemd service so NetBox survives reboots:

```bash
sudo tee /etc/systemd/system/netbox.service << 'EOF'
[Unit]
Description=NetBox Docker Compose Stack
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/netbox-docker
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable netbox
sudo systemctl start netbox
```

---

## Phase 6 — Initial Configuration

### Organization Structure

**Site:** `Home Lab` (Status: Active, Timezone: America/New_York)

**Tenant Group:** `Home Lab`

**Tenants** (3):
- `Infrastructure` — servers, networking, storage, automation
- `Home Services` — personal services, media, smart home
- `Lab & Learning` — Kubernetes, test environments

### Device Roles (13)

| Role | Color | Used For |
|------|-------|----------|
| Automation | Yellow | Ansible, n8n |
| CDN & Edge | Orange-Yellow | Cloudflare |
| Database Server | Orange | PostgreSQL |
| Hypervisor | Light Blue | Proxmox nodes |
| K8s Control Plane | Green | K3s master |
| K8s Worker | Light Green | K3s workers |
| Management | Pink | Rancher, NetBox |
| Media & Personal | Light Purple | Plex, personal services |
| Monitoring | Purple | Zabbix |
| Network | Dark Blue | Router, DNS |
| Reverse Proxy | Teal | Traefik |
| Security | Red | Vault |
| Storage | Gray | NAS |

### Virtualization Cluster

Navigate to **Virtualization → Clusters → Add**:
```
Name:         pxmx-cluster
Type:         Proxmox VE
Status:       Active
Site:         Home Lab
Tenant:       Infrastructure
```

### IPAM Prefixes

| Prefix | Status | Purpose |
|--------|--------|---------|
| 192.168.9.0/24 | Active | Current flat network |
| 192.168.10.0/24 | Reserved | Future VLAN 10 - Infrastructure |
| 192.168.20.0/24 | Reserved | Future VLAN 20 - Home Services |
| 192.168.30.0/24 | Reserved | Future VLAN 30 - Kubernetes |
| 192.168.40.0/24 | Reserved | Future VLAN 40 - IoT/Smart Home |
| 192.168.50.0/24 | Reserved | Future VLAN 50 - Management |

---

## Phase 7 — Device Type Import

NetBox has a community library of device types (manufacturers, models, port layouts). Import them via script rather than manually.

```bash
# Clone the library
sudo git clone https://github.com/netbox-community/devicetype-library.git \
  /opt/devicetype-library

# Install pynetbox
pip install pynetbox --break-system-packages
```

### Find Correct Manufacturer Names

Before importing, always check the exact directory name in the library:

```bash
ls /opt/devicetype-library/device-types/ | grep -i <manufacturer>
```

Common gotchas:
- HP servers → `HPE` (not `HP`)
- ASUS → `ASUS` (not `ASUSTek Computer`)
- Raspberry Pi → `Raspberry Pi` (not `Raspberry Pi Foundation`)

### Import Script

See `netbox/scripts/import-devicetypes.py` in this repo. Update the `MANUFACTURERS` list with exact directory names, then run:

```bash
python3 netbox/scripts/import-devicetypes.py
```

---

## Phase 8 — Physical Device Modeling

Add physical devices via **Devices → Devices → Add**. For each device you need:
- **Name** — your naming convention (e.g., `PXMX-HP380`)
- **Device Type** — manufacturer + model (imported in Phase 7)
- **Device Role** — functional role
- **Site** — `Home Lab`
- **Tenant** — appropriate tenant

### Adding Interfaces and IPs

After creating a device:
1. Open device → **Add Components → Interfaces** → create `eth0` (1000BASE-T)
2. Go to **IPAM → IP Addresses → Add** → fill in address, assign to device interface
3. Check **"Make this the primary IP for the device/VM"** during IP creation — saves an extra step

---

## Phase 9 — VM Modeling

### Bulk Import via CSV

NetBox supports CSV import for virtual machines. Navigate to **Virtualization → Virtual Machines → Import**:

```csv
name,status,cluster,device,role,tenant,vcpus,memory,disk
vm-name,active,pxmx-cluster,PXMX-HP380,Automation,Infrastructure,2,4096,40
```

### Custom Field: proxmox_vmid

Create a custom field to store the Proxmox VM ID — this is used as the unique identifier for automated sync:

Navigate to **Customization → Custom Fields → Add**:
```
Object type:    Virtualization > virtual machine
Type:           Integer
Name:           proxmox_vmid
Label:          Proxmox VMID
Must be unique: ✅ checked
```

This field is the foundation of the automated sync system.

---

## Phase 10 — Automated Sync

### The Problem with Manual Documentation

Any documentation maintained by humans eventually becomes inaccurate. Engineers rename VMs, create new ones, forget to update the CMDB. The solution is automation.

### Proxmox → NetBox Sync Script

The sync script (`netbox/scripts/proxmox-netbox-sync.py`) runs every 30 minutes and:
- Queries every Proxmox node for all VMs
- Matches against NetBox using `proxmox_vmid` (not name — names change, VMIDs don't)
- Creates new VMs automatically, tagged `needs-review`
- Updates status and name if changed in Proxmox
- Never deletes — flags missing VMs as offline

### Proxmox API Token Setup

Create a dedicated API token in Proxmox:

**Datacenter → Permissions → API Tokens → Add**
```
User:                 root@pam
Token ID:             netbox-sync
Privilege Separation: ❌ unchecked (must inherit root permissions)
```

**Important:** Privilege separation = YES will return empty VM lists even with authentication success. Always disable it for full access tokens.

### Cron Configuration

```bash
crontab -e
```

Add:
```
#SG Added - 3/8/2026 - sync Proxmox VMs to Netbox
*/30 * * * * /usr/bin/python3 /opt/homelab-automation/netbox/scripts/proxmox-netbox-sync.py >> /var/log/netbox-sync.log 2>&1
```

### Environment Variables

Never hardcode tokens in scripts. Use a `.env` file:

```bash
# .env (never commit this file)
PROXMOX_HOST=https://192.168.9.50:8006
PROXMOX_TOKEN=root@pam!netbox-sync=<your-token>
NETBOX_URL=http://localhost:8000
NETBOX_TOKEN=nbt_<key>.<secret>
CLUSTER_NAME=pxmx-cluster
DEFAULT_TENANT=Infrastructure
```

The `.env` file is listed in `.gitignore` — it never gets committed to version control.

---

## Lessons Learned

### NetBox 4.x Token Format Changed
NetBox 4.x uses v2 tokens (`nbt_KEY.SECRET`). The old 40-character v1 format returns `403 Invalid v1 token`. Always copy the full token at creation — the secret is only shown once.

### Proxmox Privilege Separation
A Proxmox API token with **Privilege Separation = Yes** will authenticate successfully but return empty VM lists. Always create tokens with Privilege Separation disabled for automation use.

### Name vs VMID as Identifier
Using VM names as unique identifiers causes duplicates when names change. Always use an immutable identifier — Proxmox VMIDs never change once assigned.

### Disk Display in NetBox
The VM list column header says "MB" but the disk values are stored in GB. This is a known cosmetic issue in the NetBox UI — the data is correct.

### Community Device Library Names
The `devicetype-library` directory names don't always match common manufacturer names. Always use `ls /opt/devicetype-library/device-types/ | grep -i <name>` to find the exact name before importing.

---

## Useful Commands

```bash
# Check NetBox stack status
cd /opt/netbox-docker && docker compose ps

# View NetBox logs
docker compose logs -f netbox

# Restart NetBox stack
sudo systemctl restart netbox

# Test API connectivity
curl -s -H "Authorization: Bearer nbt_KEY.SECRET" \
  http://localhost:8000/api/status/

# View sync log
tail -f /var/log/netbox-sync.log

# Run sync manually
python3 /opt/homelab-automation/netbox/scripts/proxmox-netbox-sync.py
```

---

## Access

| Method | URL | Notes |
|--------|-----|-------|
| Internal IP | http://192.168.9.150:8000 | Direct access on LAN |
| Internal DNS | http://netbox.qnet.local | Requires Pi-hole as resolver |
| External | https://netbox.ai-focus.org | Via Cloudflare tunnel |

---

*This guide documents the complete NetBox deployment for the homelab-automation project. For questions or improvements, open an issue on GitHub.*
