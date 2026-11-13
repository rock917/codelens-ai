"""Disposable, repository-private caches on the existing persistent uploads volume.

No credentials, auth decisions or chat answers are cached. Callers must establish
ownership before accessing a repository. JSON only; never deserialize executable data.
The supported deployment runs one API worker. Limits are per repository.
"""
import asyncio
from contextlib import asynccontextmanager
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
from uuid import UUID, uuid4

from app.config.settings import settings

MAX_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 2000
MAX_ENTRY = 4 * 1024 * 1024
TTL = 30 * 86400
_disk_lock = threading.RLock()
_locks = {}


def fingerprint(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest()


@lru_cache(maxsize=32)
def code_version(*files):
    root = Path(__file__).resolve().parent
    return fingerprint('cache-v1', *[(root / name).read_text(encoding='utf-8') for name in files])


def directory(repo_id):
    # This sibling of repository source trees cannot be populated by an upload.
    if str(UUID(repo_id)) != repo_id:
        raise ValueError('Invalid repository identifier')
    root = Path(settings.UPLOAD_DIR).resolve()
    parent = root / '.codelens-cache'
    target = parent / repo_id
    if parent.is_symlink() or target.is_symlink() or target.resolve().parent != parent.resolve():
        raise ValueError('Unsafe cache path')
    return target


def read(repo_id, key):
    try:
        with _disk_lock:
            path = directory(repo_id) / (fingerprint(key) + '.json')
            if path.is_symlink() or path.stat().st_size > MAX_ENTRY:
                return None
            item = json.loads(path.read_text(encoding='utf-8'))
            if item['expires'] < time.time() or item['key'] != key:
                path.unlink(missing_ok=True)
                return None
            return item['value']
    except (OSError, ValueError, TypeError, KeyError):
        return None


def write(repo_id, key, value):
    """Best effort: disk-full/corrupt caches must not break successful computation."""
    temporary = None
    try:
        payload = json.dumps(dict(key=key, value=value, expires=time.time() + TTL), allow_nan=False).encode()
        if len(payload) > MAX_ENTRY:
            return
        with _disk_lock:
            folder = directory(repo_id)
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            entries = sorted((p for p in folder.glob('*.json') if not p.is_symlink()), key=lambda p: p.stat().st_mtime)
            total = sum(p.stat().st_size for p in entries)
            while entries and (len(entries) >= MAX_ENTRIES or total + len(payload) > MAX_BYTES):
                old = entries.pop(0)
                total -= old.stat().st_size
                old.unlink(missing_ok=True)
            with tempfile.NamedTemporaryFile(dir=folder, delete=False) as output:
                temporary = output.name
                output.write(payload)
            os.replace(temporary, folder / (fingerprint(key) + '.json'))
    except (OSError, ValueError, TypeError):
        pass
    finally:
        if temporary:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass


def erase(repo_id):
    with _disk_lock:
        target = directory(repo_id)
        if target.exists():
            shutil.rmtree(target)


@asynccontextmanager
async def repository_lock(repo_id):
    """Serialize generation/deletion; waiter references prevent orphaned locks."""
    entry = _locks.setdefault(repo_id, [asyncio.Lock(), 0])
    entry[1] += 1
    try:
        async with entry[0]:
            yield
    finally:
        entry[1] -= 1
        if entry[1] == 0:
            del _locks[repo_id]


async def generated(repo_id, key, produce, force=False, validate=None):
    before = await asyncio.to_thread(read, repo_id, key)
    async with repository_lock(repo_id):
        if validate is not None:
            await validate()
        saved = await asyncio.to_thread(read, repo_id, key)
        if isinstance(saved, dict) and isinstance(saved.get('result'), str) and saved['result'].strip():
            # Concurrent refreshes reuse the first new generation.
            if not force or saved != before:
                return saved['result'], True
        result = await produce()
        if not isinstance(result, str) or not result.strip():
            raise ValueError('The AI returned an empty summary. Please retry.')
        await asyncio.to_thread(write, repo_id, key, {'result': result, 'generation': uuid4().hex})
        return result, False
