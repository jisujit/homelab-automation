# homelab-automation

> **Enterprise-grade homelab for real-world learning** — a production-quality infrastructure automation platform built on self-hosted, open-source technologies.

---

## Vision

This repository represents my approach to bridging the gap between enterprise IT theory and hands-on practical implementation. Rather than using cloud-managed services or simplified tutorials, every component here is deployed, configured, and automated the way a real enterprise environment would be — because that's how you actually learn.

The philosophy is simple:

- **Build it like it matters** — production patterns, not quick hacks
- **Automate everything** — if you do it twice, script it
- **Document as you go** — your future self is your most important audience
- **Learn by doing** — theory without implementation is just reading

This is not a static homelab. It's a living, evolving platform that grows as my skills and ambitions grow.

---

## Infrastructure Overview

A 3-node Proxmox VE cluster running 18+ virtual machines across enterprise-grade hardware:

| Node | Hardware | Role | Resources |
|------|----------|------|-----------|
| PXMX-HP380 | HP ProLiant DL380 Gen6 | Primary workloads | 24 cores, 71GB RAM |
| PXMX-HP360 | HP ProLiant DL360 Gen7 | Database / Kubernetes | 24 cores, 157GB RAM |
| PXMX-ASUS-Laptop | ASUS Q304U | Development / Testing | 4 cores, 6GB RAM |

**Storage:** Synology DS220+ NAS (3.5TB) providing shared storage via NFS/SMB

**Network:** 192.168.9.0/24 flat network (VLAN segmentation planned)

---

## Core Stack

### Infrastructure & Automation
| Service | VM | IP | Purpose |
|---------|----|----|---------|
| NetBox 4.5.4 | netbox (720) | 192.168.9.150 | Network Source of Truth / CMDB |
| Ansible AAP | rhel-AAP (9000) | 192.168.9.40 | Enterprise automation platform |
| HashiCorp Vault | vaultrancher (770) | 192.168.9.121 | Secrets management |
| Traefik | traefik-flame (810) | 192.168.9.120 | Reverse proxy / SSL termination |
| Zabbix | zabbix-server (820) | 192.168.9.122 | Infrastructure monitoring |

### AI & Automation
| Service | VM | IP | Purpose |
|---------|----|----|---------|
| n8n | n8n-automation (830) | 192.168.9.128 | Workflow automation |
| Ollama / LocalAI | llm-server (840) | 192.168.9.184 | Local LLM inference |
| OpenClaw | openclaw (850) | — | Agentic AI platform |

### Data & Kubernetes
| Service | VM | IP | Purpose |
|---------|----|----|---------|
| PostgreSQL 16 | postgresqlDB-server (610) | 192.168.9.123 | Primary database |
| K3s Master | k3m (700) | 192.168.9.7 | Kubernetes control plane |
| K3s Worker 1 | k3w3 (703) | 192.168.9.9 | Kubernetes worker |
| K3s Worker 2 | k3w2 (706) | 192.168.9.10 | Kubernetes worker |
| Paperless-NGX | paperless-ngx (401) | 192.168.9.180 | Document management |

---

## Repository Structure

```
homelab-automation/
├── .env.example              # Environment variable template (copy to .env)
├── .gitignore                # Protects secrets - .env never committed
├── README.md                 # This file
│
├── netbox/
│   ├── scripts/
│   │   ├── proxmox-netbox-sync.py    # Main sync engine (runs every 30min via cron)
│   │   ├── import-devicetypes.py     # Bulk import device types from community library
│   │   ├── assign-vm-ips.py          # Assign IPs to VMs via API
│   │   ├── backfill-vmids.py         # Backfill proxmox_vmid custom field
│   │   ├── cleanup-duplicates.py     # Remove manually created VM duplicates
│   │   └── fix-vm-ips.py             # Correct IP addresses after initial import
│   └── docs/
│       └── netbox-install-guide.md   # Full NetBox deployment walkthrough
│
├── terraform/                # Coming soon - Proxmox VM provisioning
├── ansible/                  # Coming soon - Configuration management playbooks
└── docs/
    └── snow-integration.md   # Coming soon - ServiceNow CMDB integration roadmap
```

---

## Key Automation: Proxmox → NetBox Sync

The centerpiece of this repo is the **Proxmox → NetBox sync engine** — a script that automatically keeps NetBox (the source of truth) synchronized with the actual state of the Proxmox cluster.

### How it works

```
Every 30 minutes (via cron):

Proxmox API → query all nodes → get all VMs + status
      ↓
Compare against NetBox using Proxmox VMID as unique identifier
      ↓
New VM found?      → Auto-create in NetBox + tag 'needs-review'
VM status changed? → Update NetBox automatically
VM name changed?   → Sync the new name to NetBox
```

### Why VMID not VM name?

VM names change. VMIDs never do. Using the Proxmox VMID as the unique identifier means:
- Renaming a VM in Proxmox updates NetBox — no duplicates
- The sync is idempotent — safe to run as many times as you want
- This is the same pattern used in enterprise CMDB integrations

### Setup

```bash
# Clone the repo
git clone https://github.com/jisujit/homelab-automation.git /opt/homelab-automation

# Configure environment
cp .env.example .env
nano .env  # fill in your Proxmox and NetBox tokens

# Test the sync
python3 netbox/scripts/proxmox-netbox-sync.py

# Add cron job (every 30 minutes)
# */30 * * * * /usr/bin/python3 /opt/homelab-automation/netbox/scripts/proxmox-netbox-sync.py >> /var/log/netbox-sync.log 2>&1
```

---

## Security Approach

- **Secrets in environment variables** — never hardcoded in scripts
- **.env gitignored** — tokens never committed to version control
- **HashiCorp Vault** — centralized secrets management for all services
- **Dedicated API tokens** — separate tokens per service with minimum required permissions
- **Cloudflare Tunnels** — external access without open firewall ports

---

## Learning Objectives & Roadmap

### Completed
- [x] Proxmox VE cluster (3 nodes)
- [x] NetBox as infrastructure source of truth
- [x] Proxmox → NetBox automated sync
- [x] Local LLM inference (Ollama)
- [x] n8n workflow automation with LLM integration
- [x] K3s Kubernetes cluster
- [x] HashiCorp Vault for secrets management
- [x] Centralized monitoring (Zabbix)

### In Progress
- [ ] Traefik reverse proxy with Vault PKI certificates
- [ ] Pi-hole as primary internal DNS resolver
- [ ] Comprehensive automated backup strategy

### Planned
- [ ] Terraform IaC for Proxmox VM provisioning
- [ ] Ansible playbooks for configuration management
- [ ] VLAN network segmentation
- [ ] ServiceNow CMDB integration (NetBox as feeder system)
- [ ] GitHub Actions CI/CD pipeline for infrastructure changes
- [ ] GitOps workflow for Kubernetes deployments

---

## The Bigger Picture: Why This Matters

Most enterprises struggle to maintain accurate CMDBs because they rely on humans to update them manually. This creates a well-known failure pattern:

```
Manual updates → stale data → nobody trusts it → nobody updates it → worse data
```

This repo demonstrates the correct pattern:

```
Infrastructure APIs → automated sync → NetBox (accurate) → feeds downstream systems
```

When you apply this to enterprise scale — with ServiceNow as the ITSM layer consuming from NetBox — you solve the CMDB accuracy problem that plagues most large organizations.

---

## Connect

Built by an IT professional returning to hands-on technical work, using a homelab as a platform for real enterprise learning.

*"Don't just study enterprise technology — run it."*
