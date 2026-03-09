#!/usr/bin/env python3
"""Delete manually created VMs that have Proxmox equivalents"""
import pynetbox

nb = pynetbox.api(
    'http://localhost:8000',
    token='nbt_vpTnx5y7y0HH.JbBMAzfSiXJc75BhkJ90M77AzG7GrcbfJELNLyWC'
)

# These are the manually created VMs with no VMID - safe to delete
# Their Proxmox equivalents already exist with correct VMIDs
to_delete = [
    'k3s-master',
    'k3s-worker',
    'k3s-worker3',
    'n8n',
    'ollama-localai',
    'postgresql',
    'rhel-ansible',
    'vault-rancher',
    'zabbix',
]

for name in to_delete:
    vm = nb.virtualization.virtual_machines.get(name=name)
    if vm:
        # Check it has no VMID (confirm it's the manual one)
        if not vm.custom_fields.get('proxmox_vmid'):
            vm.delete()
            print(f"  🗑️  Deleted duplicate: {name}")
        else:
            print(f"  ⚠️  Skipped {name} — has VMID, keeping it")
    else:
        print(f"  ℹ️  Not found: {name}")
