"""Validate archives before extraction; bound disk and decompression work."""
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile
from app.config.settings import settings


def ensure_disk_space(directory):
    Path(directory).mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(directory).free < settings.MIN_FREE_DISK_MB * 1024 * 1024:
        raise ValueError('Storage is temporarily full. Please try again later. No analysis credit was used.')


def extract_safe(zip_path, directory):
    ensure_disk_space(directory)
    root = Path(directory).resolve()
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if len(members) > settings.MAX_REPOSITORY_FILES:
            raise ValueError(f'Archive exceeds {settings.MAX_REPOSITORY_FILES} entries. No credit was used.')
        maximum = settings.MAX_EXTRACTED_SIZE_MB * 1024 * 1024
        total = 0
        names = set()
        for member in members:
            path = PurePosixPath(member.filename.replace('\\', '/'))
            mode = member.external_attr >> 16
            if (path.is_absolute() or '..' in path.parts or ':' in str(path)
                    or stat.S_ISLNK(mode) or member.flag_bits & 1
                    or not (root / str(path)).resolve().is_relative_to(root)):
                raise ValueError('Archive contains unsafe paths, links, or encrypted entries. No credit was used.')
            name = str(path).casefold()
            if name in names:
                raise ValueError('Archive contains duplicate paths. No credit was used.')
            names.add(name)
            total += member.file_size
            if total > maximum:
                raise ValueError(f'Extracted archive exceeds {settings.MAX_EXTRACTED_SIZE_MB}MB. No credit was used.')
        written = 0
        for member in members:
            target = root / member.filename.replace('\\', '/')
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open('wb') as output:
                while block := source.read(1024 * 1024):
                    written += len(block)
                    if written > maximum:
                        raise ValueError('Archive expands beyond the storage limit. No credit was used.')
                    output.write(block)


def validate_directory(directory):
    total, count = 0, 0
    for root, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = [d for d in dirs if d != '.git']
        for name in files:
            path = Path(root) / name
            if path.is_symlink():
                continue
            count += 1
            total += path.stat().st_size
            if count > settings.MAX_REPOSITORY_FILES or total > settings.MAX_EXTRACTED_SIZE_MB * 1024 * 1024:
                raise ValueError('Repository exceeds the file count or extracted size limit. No credit was used.')
