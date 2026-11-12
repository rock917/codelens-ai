"""On the Azure host: restore the latest ops backup into disposable, offline containers.

Run as root. No production writes, no secrets printed, no uploaded source executed.
Requires the deployed ops.py and postgres:17 image already present.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

spec = importlib.util.spec_from_file_location('ops', sys.argv[1] if len(sys.argv) > 1 else '/opt/codelens/ops.py')
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)
report = json.loads((ops.STATE / 'backup.json').read_text())
backup = Path(report['directory'])
assert backup.resolve().parent == ops.BACKUPS.resolve() and not backup.is_symlink()
manifest = json.loads((backup / 'manifest.json').read_text())
for name in ('database.dump', 'storage.tar.gz'):
    with (backup / name).open('rb') as source:
        digest = hashlib.sha256()
        while block := source.read(1024 * 1024):
            digest.update(block)
        assert digest.hexdigest() == manifest['sha256'][name]

name = 'codelens-backup-restore-rehearsal'
assert not ops.run(['docker', 'ps', '-aq', '--filter', 'name=^/' + name + '$']).strip(), 'Existing rehearsal container; inspect first'
ops.run(['docker', 'run', '-d', '--name', name, '--network', 'none',
         '--tmpfs', '/var/lib/postgresql/data:rw,size=512m', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
         '--mount', f'type=bind,source={backup},target=/backup,readonly', 'postgres:17'])
try:
    for attempt in range(30):
        try:
            ops.run(['docker', 'exec', name, 'pg_isready', '-U', 'postgres'])
            break
        except RuntimeError:
            time.sleep(1)
    else:
        raise RuntimeError('Isolated PostgreSQL did not start')
    ops.run(['docker', 'exec', name, 'pg_restore', '-U', 'postgres', '-d', 'postgres',
             '--clean', '--if-exists', '--no-owner', '--no-privileges', '--exit-on-error', '/backup/database.dump'])
    count = ops.run(['docker', 'exec', name, 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-c',
                    "SELECT count(*) FROM pg_tables WHERE schemaname='public'"]).decode().strip()
    assert int(count) >= 11, 'Expected application, account usage, and admission tables'
    # SQL only aggregates; source files and conversations are never printed.
    ops.run(['docker', 'exec', name, 'psql', '-U', 'postgres', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-At', '-c',
             'SELECT count(*) FROM repositories; SELECT count(*) FROM conversations; SELECT count(*) FROM messages; SELECT count(*) FROM analysis_admissions;'])
    code = """
import tarfile
from pathlib import Path
import chromadb
with tarfile.open('/backup/storage.tar.gz') as archive:
    archive.extractall('/restore', filter='data')
assert Path('/restore/uploads').is_dir()
assert Path('/restore/chroma').is_dir()
client = chromadb.PersistentClient(path='/restore/chroma')
for collection in client.list_collections():
    client.get_collection(collection.name).count()
print('Storage archive extracted; Chroma collections opened successfully.')
"""
    ops.run(['docker', 'run', '--rm', '--network', 'none', '--tmpfs', '/restore:rw,size=512m',
             '--mount', f'type=bind,source={backup},target=/backup,readonly',
             manifest['backend_image'], 'python', '-c', code])
    print('Backup restore rehearsal passed: checksums, PostgreSQL tables/data, storage extraction and Chroma collections. Production data unchanged.')
finally:
    ops.run(['docker', 'rm', '-f', name])
