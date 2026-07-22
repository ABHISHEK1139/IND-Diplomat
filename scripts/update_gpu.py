import yaml

with open('docker-compose.yml', 'r') as f:
    compose = yaml.safe_load(f)

gpu_deploy = {
    'resources': {
        'reservations': {
            'devices': [
                {
                    'driver': 'nvidia',
                    'count': 'all',
                    'capabilities': ['gpu']
                }
            ]
        }
    }
}

for service_name in ['web', 'worker', 'scheduler', 'guardian']:
    if service_name in compose.get('services', {}):
        compose['services'][service_name]['deploy'] = gpu_deploy

with open('docker-compose.yml', 'w') as f:
    yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

print('Successfully added GPU passthrough to web, worker, scheduler, and guardian services.')
