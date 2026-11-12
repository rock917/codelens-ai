"""Test backup failure/recovery and retention without Docker, credentials, or production data."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

if sys.platform == 'win32':
    sys.modules['fcntl'] = types.SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *args: None)
spec = importlib.util.spec_from_file_location('ops', Path(__file__).resolve().parents[1] / 'deploy/azure-vm/ops.py')
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


class BackupChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.calls = []
        self.info = {'State': {'Running': True}, 'Image': 'dummy-image', 'Mounts': [
            {'Destination': '/data', 'Type': 'volume', 'Name': 'dummy-volume'}]}
        self.patches = [patch.object(ops, 'STATE', self.root / 'state'),
                        patch.object(ops, 'BACKUPS', self.root / 'automatic'),
                        patch.object(ops, 'container', return_value=self.info),
                        patch.object(ops, 'query', return_value='0'),
                        patch.object(ops, 'pg_command', return_value=(['docker', 'run', '--rm'], {})),
                        patch.object(ops.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=10 * 1024**3)),
                        patch.object(ops, 'run', side_effect=self.fake_run)]
        for item in self.patches:
            item.start()
        self.addCleanup(self.temp.cleanup)
        for item in self.patches:
            self.addCleanup(item.stop)

    def fake_run(self, args, **kwargs):
        self.calls.append(args)
        if 'pg_dump' in args:
            stage = next(ops.BACKUPS.glob('.partial-*'))
            (stage / 'database.dump').write_bytes(b'dummy dump')
        if 'dummy-image' in args:
            stage = next(ops.BACKUPS.glob('.partial-*'))
            with tarfile.open(stage / 'storage.tar.gz', 'w:gz') as archive:
                item = tarfile.TarInfo('uploads/example.txt')
                item.size = 4
                archive.addfile(item, io.BytesIO(b'test'))
        return b''

    def test_success_retention_and_daily_skip(self):
        ops.BACKUPS.mkdir()
        manual = self.root / 'manual.dump'
        manual.write_bytes(b'keep')
        for day in range(1, 9):
            old = ops.BACKUPS / f'backup-202001{day:02d}T000000Z'
            old.mkdir()
            (old / 'manifest.json').write_text('{}')
        ops.backup()
        self.assertEqual(len(list(ops.BACKUPS.glob('backup-*'))), 7)
        self.assertTrue(manual.exists())
        self.assertIn(['docker', 'start', ops.CONTAINER], self.calls)
        report = json.loads((ops.STATE / 'backup.json').read_text())
        manifest = json.loads((Path(report['directory']) / 'manifest.json').read_text())
        self.assertEqual(set(manifest['sha256']), {'database.dump', 'storage.tar.gz'})
        self.assertFalse((ops.STATE / 'backup-paused').exists())
        self.calls.clear()
        ops.backup()
        self.assertEqual(self.calls, [])

    def test_failed_archive_restarts_api_without_rotating_backups(self):
        original = self.fake_run
        def fail(args, **kwargs):
            if 'dummy-image' in args:
                raise RuntimeError('Simulated archive failure')
            return original(args, **kwargs)
        with patch.object(ops, 'run', side_effect=fail):
            with self.assertRaises(RuntimeError):
                ops.backup()
        self.assertIn(['docker', 'start', ops.CONTAINER], self.calls)
        self.assertFalse((ops.STATE / 'backup.json').exists())
        self.assertEqual(list(ops.BACKUPS.glob('backup-*')), [])
        ops.backup()
        self.assertEqual(list(ops.BACKUPS.glob('.partial-*')), [])

    def test_recovery_removes_only_backup_helpers_before_start(self):
        ops.STATE.mkdir()
        (ops.STATE / 'backup-paused').touch()
        def fake(args, **kwargs):
            self.calls.append(args)
            return b'helper-id' if args[1] == 'ps' else b''
        with patch.object(ops, 'run', side_effect=fake):
            ops.recover()
        removed = [args[-1] for args in self.calls if args[1:3] == ['rm', '-f']]
        self.assertEqual(removed, list(ops.HELPERS))
        self.assertEqual(self.calls[-1], ['docker', 'start', ops.CONTAINER])

    def test_busy_and_low_disk_never_stop_api(self):
        with patch.object(ops, 'query', return_value='1'):
            ops.backup()
        self.assertEqual(self.calls, [])
        with patch.object(ops.shutil, 'disk_usage', return_value=types.SimpleNamespace(free=1024)):
            with self.assertRaises(RuntimeError):
                ops.backup()
        self.assertEqual(self.calls, [])

    def test_partial_cleanup_refuses_paths_outside_backup_directory(self):
        outside = self.root / '.partial-20200101T000000Z'
        outside.mkdir()
        with self.assertRaises(RuntimeError):
            ops.remove_partial(outside)
        self.assertTrue(outside.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
