#!/usr/bin/env python3
"""
Proxmox → NetBox Sync Script v2
Uses Proxmox VMID as unique identifier - never creates duplicates
New VMs auto-created and tagged 'needs-review'
Reads configuration from environment variables or .env file
"""

import requests
import pynetbox
import urllib3
import os
from datetime import datetime
from pathlib import Path

# Load .env file if it exists
env_file = Path(__file__).parent.parent.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Configuration from environment ─────────────────────────────
PROXMOX_HOST   = os.environ['PROXMOX_HOST']
PROXMOX_TOKEN  = os.environ['PROXMOX_TOKEN']
NETBOX_URL     = os.environ['NETBOX_URL']
NETBOX_TOKEN   = os.environ['NETBOX_TOKEN']
CLUSTER_NAME   = os.environ.get('CLUSTER_NAME', 'pxmx-cluster')
DEFAULT_TENANT = os.environ.get('DEFAULT_TENANT', 'Infrastructure')
REVIEW_TAG     = 'needs-review'

NODE_MAP = {
    'hpdl380':  'PXMX-HP380',
    'pve':      'PXMX-HP360',
    'pve3asus': 'PXMX-ASUS-Laptop',
}

STATUS_MAP = {
    'running': 'active',
    'stopped': 'offline',
    'paused':  'staged',
}

IGNORE_VMIDS = [702]  # Broken k3s clone - delete from Proxmox when ready

# ── Proxmox API ─────────────────────────────────────────────────
class ProxmoxAPI:
    def __init__(self, host, token):
        self.host = host
        self.headers = {
            'Authorization': f'PVEAPIToken={token}',
            'Accept': 'application/json',
        }

    def get(self, path):
        url = f'{self.host}/api2/json{path}'
        r = requests.get(url, headers=self.headers, verify=False)
        r.raise_for_status()
        return r.json().get('data', [])

    def get_nodes(self):
        return self.get('/nodes')

    def get_vms(self, node):
        return self.get(f'/nodes/{node}/qemu')

    def get_vm_ip(self, node, vmid):
        try:
            interfaces = self.get(
                f'/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces'
            )
            if not isinstance(interfaces, list):
                return None
            for iface in interfaces:
                if not isinstance(iface, dict):
                    continue
                if iface.get('name') in ('lo', 'docker0'):
                    continue
                for addr in iface.get('ip-addresses', []):
                    if not isinstance(addr, dict):
                        continue
                    if addr.get('ip-address-type') == 'ipv4':
                        ip = addr.get('ip-address', '')
                        if ip and not ip.startswith('127.'):
                            return f"{ip}/24"
        except Exception:
            pass
        return None

# ── NetBox Helpers ──────────────────────────────────────────────
def get_or_create_tag(nb, tag_name):
    tag = nb.extras.tags.get(name=tag_name)
    if not tag:
        tag = nb.extras.tags.create(
            name=tag_name,
            slug=tag_name.replace(' ', '-')
        )
    return tag

def find_vm_by_vmid(nb, vmid):
    results = list(nb.virtualization.virtual_machines.filter(
        cf_proxmox_vmid=vmid
    ))
    return results[0] if results else None

def assign_ip_to_vm(nb, vm, ip_address):
    existing_iface = nb.virtualization.interfaces.get(
        virtual_machine_id=vm.id,
        name='eth0'
    )
    if not existing_iface:
        existing_iface = nb.virtualization.interfaces.create(
            virtual_machine=vm.id,
            name='eth0',
            type='virtual',
        )
    existing_ip = nb.ipam.ip_addresses.get(address=ip_address)
    if not existing_ip:
        existing_ip = nb.ipam.ip_addresses.create(
            address=ip_address,
            status='active',
            assigned_object_type='virtualization.vminterface',
            assigned_object_id=existing_iface.id,
        )
    vm.primary_ip4 = existing_ip.id
    vm.save()
    return ip_address

# ── Main Sync ───────────────────────────────────────────────────
def sync():
    print(f"\n{'='*60}")
    print(f"Proxmox → NetBox Sync v2 (VMID-based)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    pve = ProxmoxAPI(PROXMOX_HOST, PROXMOX_TOKEN)
    nb  = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

    cluster = nb.virtualization.clusters.get(name=CLUSTER_NAME)
    tag     = get_or_create_tag(nb, REVIEW_TAG)
    tenant  = nb.tenancy.tenants.get(name=DEFAULT_TENANT)

    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

    nodes = pve.get_nodes()
    print(f"📡 Found {len(nodes)} Proxmox nodes\n")

    for node_data in nodes:
        node_name   = node_data['node']
        device_name = NODE_MAP.get(node_name)
        print(f"🖥️  Node: {node_name} → {device_name or 'UNMAPPED'}")

        try:
            vms = pve.get_vms(node_name)
        except Exception as e:
            print(f"  ❌ Could not query node {node_name}: {e}\n")
            stats['errors'] += 1
            continue

        if not vms:
            print(f"  ℹ️  No VMs found on this node\n")
            continue

        for vm in sorted(vms, key=lambda x: x['vmid']):
            vmid   = vm['vmid']
            if vmid in IGNORE_VMIDS:
                print(f"\n  VM {vmid}: {vm['name']} — IGNORED (in ignore list)")
                continue

            name   = vm['name']
            status = STATUS_MAP.get(vm['status'], 'staged')
            vcpus  = int(vm.get('cpus', 1))
            memory = int(vm.get('maxmem', 0)) // (1024 * 1024)
            disk   = int(vm.get('maxdisk', 0)) // (1024 * 1024 * 1024)

            print(f"\n  VM {vmid}: {name} [{vm['status']}]")

            existing = find_vm_by_vmid(nb, vmid)

            if existing:
                changed = False
                if existing.name != name:
                    print(f"    🔄 Name: '{existing.name}' → '{name}'")
                    existing.name = name
                    changed = True
                nb_status = existing.status.value if existing.status else None
                if nb_status != status:
                    print(f"    🔄 Status: {nb_status} → {status}")
                    existing.status = status
                    changed = True
                if changed:
                    existing.save()
                    stats['updated'] += 1
                else:
                    print(f"    ✅ In sync")
                    stats['skipped'] += 1
            else:
                print(f"    🆕 VMID {vmid} not in NetBox — creating...")
                try:
                    device = nb.dcim.devices.get(name=device_name) if device_name else None
                    unique_name = name
                    if nb.virtualization.virtual_machines.get(name=name):
                        unique_name = f"{name}-{vmid}"
                        print(f"    ⚠️  Name conflict — using '{unique_name}'")

                    new_vm = nb.virtualization.virtual_machines.create(
                        name=unique_name,
                        status=status,
                        cluster=cluster.id,
                        device=device.id if device else None,
                        tenant=tenant.id,
                        vcpus=vcpus,
                        memory=memory,
                        disk=disk,
                        tags=[tag.id],
                        custom_fields={'proxmox_vmid': vmid},
                        comments=f"Auto-synced from Proxmox. Node: {node_name} VMID: {vmid}",
                    )

                    ip = pve.get_vm_ip(node_name, vmid)
                    if ip:
                        assigned = assign_ip_to_vm(nb, new_vm, ip)
                        print(f"    🌐 IP: {assigned}")
                    else:
                        print(f"    ⚠️  No IP (guest agent unavailable)")

                    print(f"    ✅ Created — tagged '{REVIEW_TAG}'")
                    stats['created'] += 1

                except Exception as e:
                    print(f"    ❌ Error: {e}")
                    stats['errors'] += 1

        print()

    print(f"{'='*60}")
    print(f"Sync Complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Created: {stats['created']}  Updated: {stats['updated']}  "
          f"Skipped: {stats['skipped']}  Errors: {stats['errors']}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    sync()
