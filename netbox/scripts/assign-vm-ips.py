import pynetbox

nb = pynetbox.api(
    'http://localhost:8000',
    token='nbt_vpTnx5y7y0HH.JbBMAzfSiXJc75BhkJ90M77AzG7GrcbfJELNLyWC'
)

vms = [
    ('vault-rancher',  '192.168.9.121/24', 'vault-rancher.qnet.local'),
    ('traefik-flame',  '192.168.9.120/24', 'traefik.qnet.local'),
    ('zabbix',         '192.168.9.122/24', 'zabbix.qnet.local'),
    ('n8n',            '192.168.9.128/24', 'n8n.qnet.local'),
    ('ollama-localai', '192.168.9.184/24', 'ollama.qnet.local'),
    ('paperless-ngx',  '192.168.9.180/24', 'paperless.qnet.local'),
    ('postgresql',     '192.168.9.123/24', 'postgresql.qnet.local'),
    ('k3s-master',     '192.168.9.100/24', 'k3s-master.qnet.local'),
    ('k3s-worker',     '192.168.9.101/24', 'k3s-worker.qnet.local'),
    ('rhel-ansible',   '192.168.9.102/24', 'rhel-ansible.qnet.local'),
    ('netbox',         '192.168.9.150/24', 'netbox.qnet.local'),
]

for vm_name, ip, dns in vms:
    vm = nb.virtualization.virtual_machines.get(name=vm_name)
    if not vm:
        print(f"❌ VM not found: {vm_name}")
        continue

    iface = nb.virtualization.interfaces.create(
        virtual_machine=vm.id,
        name='eth0',
        type='virtual',
    )

    ip_obj = nb.ipam.ip_addresses.create(
        address=ip,
        status='active',
        dns_name=dns,
        assigned_object_type='virtualization.vminterface',
        assigned_object_id=iface.id,
    )

    vm.primary_ip4 = ip_obj.id
    vm.save()

    print(f"✅ {vm_name} → {ip}")
