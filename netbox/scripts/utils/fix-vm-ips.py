import pynetbox

nb = pynetbox.api(
    'http://localhost:8000',
    token='nbt_vpTnx5y7y0HH.JbBMAzfSiXJc75BhkJ90M77AzG7GrcbfJELNLyWC'
)

fixes = [
    ('rhel-ansible', '192.168.9.102/24', '192.168.9.40/24',  'rhel-ansible.qnet.local'),
    ('k3s-master',   '192.168.9.100/24', '192.168.9.7/24',   'k3s-master.qnet.local'),
    ('k3s-worker',   '192.168.9.101/24', '192.168.9.9/24',   'k3s-worker2.qnet.local'),
]

for vm_name, old_ip, new_ip, dns in fixes:
    ip_obj = nb.ipam.ip_addresses.get(address=old_ip)
    if not ip_obj:
        print(f"❌ IP not found: {old_ip}")
        continue
    ip_obj.address = new_ip
    ip_obj.dns_name = dns
    ip_obj.save()
    print(f"✅ {vm_name}: {old_ip} → {new_ip}")
