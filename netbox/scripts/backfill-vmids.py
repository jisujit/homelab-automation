#!/usr/bin/env python3
"""
Backfill proxmox_vmid custom field on existing NetBox VMs
Matches by name to find the right VMID
"""
import requests, pynetbox, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROXMOX_HOST  = 'https://192.168.9.50:8006'
PROXMOX_TOKEN = 'root@pam!netbox-sync=0930ea12-10bc-43f1-8504-ab79b7b9ead7'
NETBOX_URL    = 'http://localhost:8000'
NETBOX_TOKEN  = 'nbt_vpTnx5y7y0HH.JbBMAzfSiXJc75BhkJ90M77AzG7GrcbfJELNLyWC'

headers = {'Authorization': f'PVEAPIToken={PROXMOX_TOKEN}', 'Accept': 'application/json'}
nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

# Build VMID map from Proxmox: {vm_name: vmid}
vmid_map = {}
nodes = requests.get(f'{PROXMOX_HOST}/api2/json/nodes', headers=headers, verify=False).json()['data']
for node in nodes:
    try:
        vms = requests.get(f'{PROXMOX_HOST}/api2/json/nodes/{node["node"]}/qemu', headers=headers, verify=False).json()['data']
        for vm in vms:
            vmid_map[vm['name']] = vm['vmid']
            print(f"  Found in Proxmox: {vm['name']} → VMID {vm['vmid']}")
    except:
        pass

print(f"\nBackfilling {len(vmid_map)} VMIDs into NetBox...\n")

# Update all NetBox VMs that have matching Proxmox names
for nb_vm in nb.virtualization.virtual_machines.all():
    if nb_vm.name in vmid_map:
        vmid = vmid_map[nb_vm.name]
        nb_vm.custom_fields['proxmox_vmid'] = vmid
        nb_vm.save()
        print(f"  ✅ {nb_vm.name} → VMID {vmid}")
    else:
        print(f"  ⚠️  {nb_vm.name} → not found in Proxmox (manually created)")
