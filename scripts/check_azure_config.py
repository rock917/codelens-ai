"""Validate Azure Compose using dummy settings only, without starting containers.

Requires Docker Compose v2, but no running Docker daemon, Azure login or network.
Never loads repository dotenv files or displays a rendered environment.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DUMMY = {
    'DATABASE_URL': 'postgresql+asyncpg://test:test@database.invalid/test',
    'GROQ_API_KEY': 'test-only-not-a-secret',
    'SUPABASE_URL': 'https://test.supabase.co',
    'SUPABASE_PUBLISHABLE_KEY': 'test-only-public-key',
    'GROQ_MODEL': 'test-model',
    'FRONTEND_URL': 'https://frontend.example.com',
    'API_DOMAIN': 'api.example.com',
}


def main():
    # Remove Compose controls and explicitly replace every interpolated variable.
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith('COMPOSE_')}
    environment.update(DUMMY)
    with tempfile.TemporaryDirectory(prefix='codelens-compose-check-') as directory:
        empty_env = Path(directory) / 'empty-settings.txt'
        empty_env.write_text('', encoding='utf-8')
        command = ['docker', 'compose', '--env-file', str(empty_env),
                   '-f', str(ROOT / 'deploy/azure-vm/compose.yaml'),
                   '-f', str(ROOT / 'deploy/azure-vm/compose.https.yaml')]
        result = subprocess.run(command + ['config', '--no-env-resolution', '--format', 'json'], cwd=directory,
                                env=environment, capture_output=True, text=True)
        if result.returncode:
            raise SystemExit('Compose validation failed. Check the Docker Compose installation and configuration.')
        config = json.loads(result.stdout)
        backend = config['services']['backend']
        proxy = config['services']['proxy']
        assert all(p.get('host_ip') == '127.0.0.1' for p in backend['ports']), 'Backend port must stay private'
        assert backend['command'][-2:] == ['--workers', '1'], 'In-process jobs require one worker'
        assert backend['environment']['DEBUG'] == 'false'
        assert backend['environment']['FRONTEND_URL'] == DUMMY['FRONTEND_URL']
        assert any(v['type'] == 'volume' and v['target'] == '/data' for v in backend['volumes'])
        assert {str(p['published']) for p in proxy['ports']} == {'80', '443'}
        assert proxy['depends_on']['backend']['condition'] == 'service_healthy'
        assert any(v['target'] == '/data' and v['type'] == 'volume' for v in proxy['volumes'])
        mount = next(v for v in proxy['volumes'] if v['target'] == '/etc/caddy/Caddyfile')
        assert Path(mount['source']).resolve() == (ROOT / 'deploy/azure-vm/Caddyfile').resolve()
        assert mount['read_only'] is True
        for required in ('DATABASE_URL', 'GROQ_API_KEY', 'SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'API_DOMAIN'):
            missing = dict(environment)
            missing.pop(required, None)
            result = subprocess.run(command + ['config', '--quiet'], cwd=directory,
                                    env=missing, capture_output=True, text=True)
            assert result.returncode != 0, f'{required} must be required'
    print('Azure Compose passed: private API port, one worker, persistent storage, HTTPS proxy and required settings.')
    print('No images built, containers started, real credentials loaded or Azure resources created.')


if __name__ == '__main__':
    main()
