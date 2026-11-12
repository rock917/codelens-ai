#!/usr/bin/env python3
"""Local-only backup and health checks. Never prints credentials or user records."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import urllib.request
from urllib.parse import unquote, urlsplit

STATE = Path('/var/lib/codelens-ops')
BACKUPS = Path('/home/azureuser/codelens-backups/automatic')
CONTAINER = 'codelens-backend-1'
HELPERS = ('codelens-backup-database', 'codelens-backup-storage')
os.umask(0o077)


def run(args, **kwargs):
    result = subprocess.run(args, capture_output=True, timeout=kwargs.pop('timeout', 300), **kwargs)
    if result.returncode:
        raise RuntimeError('Operation failed: ' + Path(args[0]).name)
    return result.stdout


def save(name, value):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = STATE / (name + '.tmp')
    temp.write_text(json.dumps(value, indent=2))
    temp.replace(STATE / name)


def container():
    return json.loads(run(['docker', 'inspect', CONTAINER]))[0]


def pg_command(info):
    values = dict(item.split('=', 1) for item in info['Config']['Env'])
    url = urlsplit(values['DATABASE_URL'].replace('postgresql+asyncpg:', 'postgresql:'))
    if url.scheme not in ('postgres', 'postgresql') or not url.hostname:
        raise RuntimeError('Expected PostgreSQL configuration')
    env = {**os.environ, 'PGHOST': url.hostname, 'PGPORT': str(url.port or 5432),
           'PGUSER': unquote(url.username), 'PGPASSWORD': unquote(url.password),
           'PGDATABASE': url.path.lstrip('/'), 'PGSSLMODE': 'require', 'PGCONNECT_TIMEOUT': '15',
           'PGOPTIONS': '-c statement_timeout=240000'}
    args = ['docker', 'run', '--rm', '-i']
    for key in ('PGHOST', 'PGPORT', 'PGUSER', 'PGPASSWORD', 'PGDATABASE', 'PGSSLMODE', 'PGCONNECT_TIMEOUT', 'PGOPTIONS'):
        args += ['-e', key]
    return args, env


def query(info, sql):
    args, env = pg_command(info)
    return run(args + ['postgres:17', 'psql', '-X', '-At', '-v', 'ON_ERROR_STOP=1'],
               env=env, input=sql.encode(), timeout=45).decode().strip()


def recover():
    marker = STATE / 'backup-paused'
    if marker.exists():
        # A timed-out Docker client can leave its container running. Stop our helpers
        # before restarting writers; never remove application containers or volumes.
        for name in HELPERS:
            found = run(['docker', 'ps', '-aq', '--filter', 'name=^/' + name + '$']).strip()
            if found:
                run(['docker', 'rm', '-f', name], timeout=60)
        run(['docker', 'start', CONTAINER], timeout=60)
        marker.unlink()


def remove_partial(path):
    if (path.resolve().parent != BACKUPS.resolve() or path.is_symlink()
            or not re.fullmatch(r'\.partial-\d{8}T\d{6}Z', path.name)):
        raise RuntimeError('Unexpected partial backup path')
    shutil.rmtree(path)


def backup(force=False):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE / 'backup.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Backup already running.')
            return
        recover()
        if BACKUPS.exists():
            for path in BACKUPS.glob('.partial-*'):
                remove_partial(path)
        now = dt.datetime.now(dt.timezone.utc)
        last = STATE / 'backup.json'
        if not force and last.exists():
            old = json.loads(last.read_text())
            if old.get('status') == 'ok' and (now - dt.datetime.fromisoformat(old['time'])).total_seconds() < 86400:
                return
        info = container()
        if not info['State']['Running']:
            raise RuntimeError('Backend is stopped; backup deferred')
        busy = query(info, "SELECT (SELECT count(*) FROM repositories WHERE status NOT IN ('READY','FAILED')) + (SELECT count(*) FROM repository_jobs WHERE status IN ('PENDING','RUNNING'));")
        if busy != '0':
            print('Backup deferred until current jobs finish; the hourly timer will retry.')
            return
        if shutil.disk_usage('/').free < 4 * 1024**3:
            raise RuntimeError('Insufficient free space for a backup')
        mount = next(m for m in info['Mounts'] if m['Destination'] == '/data' and m['Type'] == 'volume')
        BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
        stamp = now.strftime('%Y%m%dT%H%M%SZ')
        staging = BACKUPS / ('.partial-' + stamp)
        staging.mkdir(mode=0o700)
        (STATE / 'backup-paused').touch(mode=0o600)
        try:
            run(['docker', 'stop', '--time', '30', CONTAINER], timeout=60)
            # An import may have started between the first check and the graceful stop.
            if query(info, "SELECT (SELECT count(*) FROM repositories WHERE status NOT IN ('READY','FAILED')) + (SELECT count(*) FROM repository_jobs WHERE status IN ('PENDING','RUNNING'));") != '0':
                raise RuntimeError('New work arrived; retry backup after recovery')
            args, env = pg_command(info)
            run(args + ['--name', HELPERS[0], '--mount', f'type=bind,source={staging},target=/backup', 'postgres:17',
                        'pg_dump', '--schema=public', '--format=custom', '--file=/backup/database.dump'], env=env)
            # The model download cache is reproducible and deliberately excluded.
            archive_code = "import tarfile; from pathlib import Path; t=tarfile.open('/backup/storage.tar.gz','w:gz'); [(t.add('/data/'+n,arcname=n)) for n in ('uploads','chroma') if Path('/data/'+n).exists()]; t.close()"
            run(['docker', 'run', '--rm', '--name', HELPERS[1], '--network', 'none', '--mount', f'type=volume,source={mount["Name"]},target=/data,readonly',
                 '--mount', f'type=bind,source={staging},target=/backup', info['Image'], 'python', '-c', archive_code])
        finally:
            recover()
        # Verify both artifacts can be read before publishing or rotating older backups.
        run(['docker', 'run', '--rm', '--network', 'none', '--mount', f'type=bind,source={staging},target=/backup,readonly',
             'postgres:17', 'pg_restore', '--list', '/backup/database.dump'])
        import tarfile
        with tarfile.open(staging / 'storage.tar.gz') as archive:
            for member in archive:
                if member.isfile():
                    source = archive.extractfile(member)
                    while source.read(1024 * 1024):
                        pass
        hashes = {}
        for path in staging.iterdir():
            digest = hashlib.sha256()
            with path.open('rb') as source:
                while block := source.read(1024 * 1024):
                    digest.update(block)
            hashes[path.name] = digest.hexdigest()
        (staging / 'manifest.json').write_text(json.dumps({'time': now.isoformat(), 'sha256': hashes,
            'backend_image': info['Image'], 'database_scope': 'public schema only; Supabase Auth is excluded'}, indent=2))
        final = BACKUPS / ('backup-' + stamp)
        staging.rename(final)
        save('backup.json', {'status': 'ok', 'time': now.isoformat(), 'directory': str(final)})
        # Only this tool's completed backup directories are eligible for retention cleanup.
        complete = sorted(p for p in BACKUPS.iterdir() if re.fullmatch(r'backup-\d{8}T\d{6}Z', p.name)
                          and p.is_dir() and not p.is_symlink() and (p / 'manifest.json').is_file())
        for old in complete[:-7]:
            if old.resolve().parent != BACKUPS.resolve():
                raise RuntimeError('Unexpected retention path')
            shutil.rmtree(old)
        print('Verified backup saved: ' + str(final))


def monitor():
    issues = []
    now = dt.datetime.now(dt.timezone.utc)
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=8) as response:
            if response.status != 200:
                issues.append('Backend readiness failed')
    except Exception:
        if not (STATE / 'backup-paused').exists():
            issues.append('Backend or database unavailable')
    free = shutil.disk_usage('/').free // (1024**2)
    if free < 4096:
        issues.append('Disk space below 4GB')
    try:
        last = json.loads((STATE / 'backup.json').read_text())
        age = (now - dt.datetime.fromisoformat(last['time'])).total_seconds()
        if age > 30 * 3600 or last['status'] != 'ok':
            issues.append('No successful backup within 30 hours')
    except (OSError, ValueError, KeyError):
        issues.append('No verified backup recorded')
    try:
        stalled = query(container(), "SELECT (SELECT count(*) FROM repositories WHERE status NOT IN ('READY','FAILED') AND updated_at < now() - interval '30 minutes') + (SELECT count(*) FROM repository_jobs WHERE status IN ('PENDING','RUNNING') AND updated_at < now() - interval '15 minutes');")
        if int(stalled):
            issues.append('Jobs may be stalled; inspect before restarting')
    except Exception:
        issues.append('Database job check unavailable')
    report = {'time': now.isoformat(), 'status': 'warning' if issues else 'ok', 'free_disk_mb': free, 'issues': issues}
    save('health.json', report)
    print(json.dumps(report))
    return bool(issues)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(RuntimeError('Interrupted')))
    try:
        mode = sys.argv[1]
        if mode == 'backup':
            backup('--force' in sys.argv)
        elif mode == 'recover':
            recover()
        elif mode == 'monitor':
            sys.exit(1 if monitor() else 0)
        else:
            raise ValueError('Unknown operation')
    except Exception:
        # Do not log connection strings, environment values, SQL output, or source files.
        print('CodeLens operation failed. Backend recovery will be attempted by the service.', file=sys.stderr)
        sys.exit(1)
