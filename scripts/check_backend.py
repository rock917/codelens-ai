"""Isolated backend checks: never load project dotenv files or production data.

Run with backend/venv/Scripts/python.exe scripts/check_backend.py [--real-model] [--gpu].
Real-model mode uses only an already cached model; it does not download one.
"""
import argparse
import asyncio
import io
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch
import zipfile
import uuid

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--real-model', action='store_true')
parser.add_argument('--gpu', action='store_true')
parser.add_argument('--project-fixture', action='store_true')
args = parser.parse_args()
scratch = tempfile.TemporaryDirectory(prefix='codelens-check-')
os.chdir(scratch.name)
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.update(
    SUPABASE_URL='https://auth.test',
    SUPABASE_PUBLISHABLE_KEY='test-public-key',
    GROQ_API_KEY='test-only-no-network',
    DATABASE_URL='sqlite+aiosqlite:///./test.db',
    CHROMA_PERSIST_DIR='./vectors',
    UPLOAD_DIR='./uploads',
    DEBUG='false',
    RESOURCE_GUARDS_ENABLED='false',
    USE_GPU=str(args.gpu).lower(),
    HF_HUB_OFFLINE='1',
    TRANSFORMERS_OFFLINE='1',
    HF_HUB_DISABLE_TELEMETRY='1',
    ANONYMIZED_TELEMETRY='False',
)

from httpx import ASGITransport, AsyncClient, Response
from app import auth
from sqlalchemy import select
from app.database.base import AsyncSessionLocal, engine, init_db, recover_interrupted_jobs
from app.models.repository import Repository
from app.services import repository_service as service
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from app.services.llm.groq_provider import groq_provider
from main import app
from app.config.settings import settings

USER_A = '11111111-1111-4111-8111-111111111111'
USER_B = '22222222-2222-4222-8222-222222222222'


async def fake_auth(token):
    users = {'user-a': USER_A, 'user-b': USER_B}
    if token == 'unavailable':
        return Response(503)
    if token not in users:
        return Response(401)
    return Response(200, json={'id': users[token], 'email': f'{token}@example.com', 'email_confirmed_at': '2026-01-01T00:00:00Z'})


SOURCE = 'def add(a, b):\n    return a + b\n\ndef unsafe(value):\n    return eval(value)\n'


def archive(source=SOURCE):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as zf:
        zf.writestr('sample.py', source)
        zf.writestr('web.ts', 'export function greet(name) {\n  return name;\n}\n')
    return output.getvalue()


async def fake_stream(*args, **kwargs):
    yield 'The add function adds two values.'


class BackendChecks(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from app.services.account_deletion import recently_deleted
        recently_deleted.clear()
        await init_db()
        # Each test gets its own empty schema; quota/cache tests must not share history.
        from app.database.base import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        patch.object(auth, '_fetch_user', side_effect=fake_auth).start()
        self.summary = patch.object(service, '_run_summarization_background', new=AsyncMock())
        self.summary.start()
        self.llm = patch.object(groq_provider, 'chat', new=AsyncMock(return_value='Test response'))
        self.llm.start()
        self.streaming = patch.object(groq_provider, 'stream', new=fake_stream)
        self.streaming.start()
        if not args.real_model:
            self.embedding = patch.object(embedding_service, 'embed_batch', side_effect=lambda texts: [[1.0] + [0.0] * 383 for _ in texts])
            self.embedding.start()
            self.query = patch.object(embedding_service, 'embed_text', return_value=[1.0] + [0.0] * 383)
            self.query.start()
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url='http://test', headers={'Authorization': 'Bearer user-a'})

    async def asyncTearDown(self):
        await self.client.aclose()
        patch.stopall()
        await engine.dispose()

    async def upload(self):
        response = await self.client.post('/repositories/upload', files={'file': ('sample.zip', archive() + uuid.uuid4().hex.encode(), 'application/zip')})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['id']

    async def test_summary_cache_reuse_refresh_isolation_and_model_invalidation(self):
        from app.services import result_cache
        repo = await self.upload()
        files = (await self.client.get(f'/repositories/{repo}/files')).json()
        file_id = files[0]['id']
        for path in (f'/summary/file/{file_id}', f'/summary/repository/{repo}'):
            first = await self.client.get(path)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertFalse(first.json()['cached'])
            count = groq_provider.chat.await_count
            self.assertTrue((await self.client.get(path)).json()['cached'])
            self.assertEqual(groq_provider.chat.await_count, count)
            refreshed = await self.client.get(path + '?force=true')
            self.assertFalse(refreshed.json()['cached'])
            self.assertEqual(groq_provider.chat.await_count, count + 1)
            with patch.object(groq_provider, 'model', 'different-test-model'):
                self.assertFalse((await self.client.get(path)).json()['cached'])
            self.client.headers['Authorization'] = 'Bearer user-b'
            before = groq_provider.chat.await_count
            self.assertEqual((await self.client.get(path)).status_code, 404)
            self.assertEqual(groq_provider.chat.await_count, before)
            self.client.headers['Authorization'] = 'Bearer user-a'
        self.assertTrue(result_cache.directory(repo).is_dir())
        self.assertEqual((await self.client.delete(f'/repositories/{repo}')).status_code, 200)
        self.assertFalse(result_cache.directory(repo).exists())

    async def test_summary_duplicate_requests_share_work_and_failures_are_not_cached(self):
        repo = await self.upload()
        path = f'/summary/repository/{repo}'
        started, release = asyncio.Event(), asyncio.Event()
        async def slow(*args, **kwargs):
            started.set()
            await release.wait()
            return 'Shared summary'
        with patch.object(groq_provider, 'chat', new=AsyncMock(side_effect=slow)) as model:
            first = asyncio.create_task(self.client.get(path))
            await started.wait()
            second = asyncio.create_task(self.client.get(path))
            await asyncio.sleep(.05)
            release.set()
            results = await asyncio.gather(first, second)
            self.assertEqual(sorted(r.json()['cached'] for r in results), [False, True])
            self.assertEqual(model.await_count, 1)
        from app.services import result_cache
        result_cache.erase(repo)
        with patch.object(groq_provider, 'chat', new=AsyncMock(side_effect=RuntimeError('provider unavailable'))):
            with self.assertRaises(RuntimeError):
                await self.client.get(path)
        self.assertFalse((await self.client.get(path)).json()['cached'])

    async def test_health_cache_source_rules_and_force_refresh(self):
        from app.services.analyzer import analysis_engine
        repo = await self.upload()
        path = f'/analysis/{repo}'
        first = (await self.client.post(path)).json()
        second = (await self.client.post(path)).json()
        self.assertTrue(second['cached'])
        self.assertEqual(first['job_id'], second['job_id'])
        forced = (await self.client.post(path + '?force=true')).json()
        self.assertFalse(forced['cached'])
        self.assertNotEqual(first['job_id'], forced['job_id'])
        source = Path(settings.UPLOAD_DIR, repo, 'sample.py')
        source.write_text(SOURCE + '\n# changed source\n')
        self.assertFalse((await self.client.post(path)).json()['cached'])
        with patch('app.services.result_cache.code_version', return_value='new-rules'):
            self.assertFalse((await self.client.post(path)).json()['cached'])
        used = (await self.client.get('/repositories/usage')).json()['used']
        self.assertEqual(used, 1)

    async def test_parsing_embedding_cache_and_versioned_reindex(self):
        from app.services import cached_processing, result_cache
        from app.services.parser.parser_factory import ParserFactory
        repo = await self.upload()
        with patch.object(ParserFactory, 'parse_file', wraps=ParserFactory.parse_file) as parse:
            cached_processing.parse(repo, 'cached.py', SOURCE, 'python')
            cached_processing.parse(repo, 'cached.py', SOURCE, 'python')
            self.assertEqual(parse.call_count, 1)
            cached_processing.parse(repo, 'cached.py', SOURCE + '\n# changed', 'python')
            self.assertEqual(parse.call_count, 2)
        with patch.object(embedding_service, 'embed_batch', side_effect=lambda texts: [[1., 0.] for _ in texts]) as embed:
            values = cached_processing.embed(repo, ['first', 'first', 'second'])
            self.assertEqual(len(values), 3)
            self.assertEqual(embed.call_args.args[0], ['first', 'second'])
            cached_processing.embed(repo, ['second', 'first'])
            self.assertEqual(embed.call_count, 1)
            with patch.object(settings, 'EMBEDDING_MODEL', 'changed-model'):
                cached_processing.embed(repo, ['first'])
                self.assertEqual(embed.call_count, 2)
        with patch.object(cached_processing, 'parse', wraps=cached_processing.parse):
            before = vector_store.get_chunk_count(repo)
            self.assertEqual((await self.client.post(f'/repositories/{repo}/reindex')).status_code, 200)
            self.assertEqual(vector_store.get_chunk_count(repo), before)
            await self.client.post(f'/analysis/{repo}')
            result_cache.write(repo, 'index-version', 'old-version')
            response = await self.client.post(f'/repositories/{repo}/reindex')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual((await self.client.get(f'/repositories/{repo}/status')).json()['status'], 'READY')
            self.assertEqual(vector_store.get_chunk_count(repo), before)
            health = (await self.client.get(f'/analysis/{repo}/summary')).json()
            self.assertEqual(health['analysis_status'], 'STALE')
            self.assertIsNone(health['health_score'])

    async def test_cache_corruption_expiry_bounds_and_deleted_account(self):
        from app.services import result_cache as cache
        repo = await self.upload()
        cache.write(repo, 'sample', {'safe': True})
        path = cache.directory(repo) / (cache.fingerprint('sample') + '.json')
        path.write_text('broken JSON')
        self.assertIsNone(cache.read(repo, 'sample'))
        with patch.object(cache, 'TTL', -1):
            cache.write(repo, 'expired', 'value')
        self.assertIsNone(cache.read(repo, 'expired'))
        with patch.object(cache, 'MAX_ENTRIES', 2):
            for i in range(5):
                cache.write(repo, str(i), 'value')
            self.assertLessEqual(len(list(cache.directory(repo).glob('*.json'))), 2)
        self.enable_deletion()
        with patch('app.services.account_deletion.delete_identity', new=AsyncMock()):
            response = await self.client.request('DELETE', '/account/deletion', json={'email': 'user-a@example.com', 'confirmation': 'DELETE'})
            self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(cache.directory(repo).exists())

    def enable_deletion(self):
        import time
        from pydantic import SecretStr
        patch.object(settings, 'SUPABASE_SERVICE_ROLE_KEY', SecretStr('test-admin-not-a-secret')).start()
        patch.object(auth, 'verified_sign_in_time', return_value=time.time()).start()

    async def test_account_deletion_requires_fresh_auth_and_exact_confirmation(self):
        from app.services import account_deletion as deletion
        body = {'email': 'user-a@example.com', 'confirmation': 'DELETE'}
        repo = await self.upload()
        self.assertEqual((await self.client.delete('/account/deletion')).status_code, 422)
        self.assertEqual((await self.client.request('DELETE', '/account/deletion', json=body)).status_code, 403)
        self.enable_deletion()
        with patch.object(deletion, 'delete_identity', new=AsyncMock()) as remove:
            for payload in ({**body, 'email': 'user-b@example.com'}, {**body, 'confirmation': 'delete'}):
                self.assertEqual((await self.client.request('DELETE', '/account/deletion', json=payload)).status_code, 400)
            self.assertEqual((await self.client.request('DELETE', '/account/deletion', json={**body, 'owner_id': USER_B})).status_code, 422)
            remove.assert_not_called()
        self.assertEqual((await self.client.get(f'/repositories/{repo}')).status_code, 200)

    async def test_deleted_account_cleans_sql_vectors_files_and_old_deleted_repositories(self):
        from app.services import account_deletion as deletion
        from app.models.deletion import AccountDeletion
        from app.models.usage import AnalysisAdmission, AccountUsage
        from app.models.conversation import Conversation, Message
        from sqlalchemy import func
        a = await self.upload()
        old = await self.upload()
        self.assertEqual((await self.client.delete(f'/repositories/{old}')).status_code, 200)
        self.assertTrue(Path(settings.UPLOAD_DIR, old).exists())
        await self.client.post('/chat', json={'repository_id': a, 'question': 'Explain this', 'stream': False})
        await self.client.post(f'/analysis/{a}')
        self.client.headers['Authorization'] = 'Bearer user-b'
        b = await self.upload()
        self.client.headers['Authorization'] = 'Bearer user-a'
        self.enable_deletion()
        with patch.object(deletion, 'delete_identity', new=AsyncMock()) as remove:
            response = await self.client.request('DELETE', '/account/deletion', json={'email': 'user-a@example.com', 'confirmation': 'DELETE'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'deleted')
            remove.assert_awaited_once_with(USER_A)
        # Even an Auth response fetched just before deletion cannot reopen access.
        self.assertEqual((await self.client.get('/repositories')).status_code, 401)
        self.assertFalse(Path(settings.UPLOAD_DIR, a).exists())
        self.assertFalse(Path(settings.UPLOAD_DIR, old).exists())
        names = [collection.name for collection in vector_store.get_client().list_collections()]
        self.assertNotIn('repo_' + a.replace('-', '_'), names)
        self.assertNotIn('repo_' + old.replace('-', '_'), names)
        self.assertIn('repo_' + b.replace('-', '_'), names)
        async with AsyncSessionLocal() as db:
            self.assertIsNone(await db.get(Repository, a))
            self.assertIsNone(await db.get(AccountUsage, USER_A))
            self.assertIsNone(await db.get(AccountDeletion, USER_A))
            self.assertEqual(await db.scalar(select(func.count()).select_from(AnalysisAdmission).where(AnalysisAdmission.owner_id == USER_A)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(Conversation)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(Message)), 0)
            self.assertIsNotNone(await db.get(Repository, b))
        self.client.headers['Authorization'] = 'Bearer user-b'
        self.assertEqual((await self.client.get(f'/repositories/{b}')).status_code, 200)

    async def test_deletion_failures_stay_blocked_and_retry_after_restart(self):
        from app.services import account_deletion as deletion
        from app.models.deletion import AccountDeletion
        repo = await self.upload()
        self.enable_deletion()
        body = {'email': 'user-a@example.com', 'confirmation': 'DELETE'}
        with patch.object(deletion, 'erase_storage', side_effect=OSError('fixture failure')), patch.object(deletion, 'delete_identity', new=AsyncMock()) as remove:
            response = await self.client.request('DELETE', '/account/deletion', json=body)
            self.assertEqual(response.status_code, 202, response.text)
            remove.assert_not_called()
        self.assertEqual((await self.client.get('/repositories')).status_code, 409)
        self.assertTrue((await self.client.get('/account/deletion')).json()['pending'])
        async with AsyncSessionLocal() as db:
            self.assertEqual((await db.get(AccountDeletion, USER_A)).phase, 'DATA')
        await engine.dispose()
        with patch.object(deletion, 'delete_identity', new=AsyncMock(side_effect=RuntimeError('offline'))):
            self.assertFalse(await deletion.start_deletion(USER_A))
        async with AsyncSessionLocal() as db:
            self.assertIsNone(await db.get(Repository, repo))
            self.assertEqual((await db.get(AccountDeletion, USER_A)).phase, 'AUTH')
        with patch.object(deletion, 'delete_identity', new=AsyncMock()) as remove:
            self.assertTrue(await deletion.start_deletion(USER_A))
            remove.assert_awaited_once_with(USER_A)

    async def test_deletion_refuses_active_work_and_missing_admin_configuration(self):
        from app.services import account_deletion as deletion
        from pydantic import SecretStr
        self.enable_deletion()
        body = {'email': 'user-a@example.com', 'confirmation': 'DELETE'}
        async with deletion.account_work(USER_A):
            response = await self.client.request('DELETE', '/account/deletion', json=body)
            self.assertEqual(response.status_code, 409, response.text)
        with patch.object(settings, 'SUPABASE_SERVICE_ROLE_KEY', SecretStr('')):
            self.assertFalse((await self.client.get('/account/deletion')).json()['enabled'])
            self.assertEqual((await self.client.request('DELETE', '/account/deletion', json=body)).status_code, 503)
        self.assertEqual(dict(deletion.active), {})

    async def test_token_refresh_does_not_count_as_fresh_sign_in(self):
        import base64, json, time
        now = time.time()
        def token(amr, sub=USER_A):
            claims = {'sub': sub, 'iat': now, 'amr': amr}
            return 'header.' + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=') + '.signature'
        self.assertEqual(auth.verified_sign_in_time(token([{'method': 'token_refresh', 'timestamp': now}]), USER_A), 0)
        self.assertEqual(auth.verified_sign_in_time(token([{'method': 'oauth', 'timestamp': now}], USER_B), USER_A), 0)
        self.assertEqual(auth.verified_sign_in_time(token([{'method': 'password', 'timestamp': now - 700}]), USER_A), now - 700)
        self.assertEqual(auth.verified_sign_in_time(token([{'method': 'oauth', 'timestamp': now}]), USER_A), now)

    async def test_streaming_reply_holds_account_lease_until_finished(self):
        repo = await self.upload()
        self.enable_deletion()
        started, finish = asyncio.Event(), asyncio.Event()
        async def waiting_stream(*args, **kwargs):
            started.set()
            yield 'First part'
            await finish.wait()
            yield 'Last part'
        with patch.object(groq_provider, 'stream', new=waiting_stream):
            task = asyncio.create_task(self.client.post('/chat', json={'repository_id': repo, 'question': 'Explain', 'stream': True}))
            try:
                await asyncio.wait_for(started.wait(), 10)
                response = await self.client.request('DELETE', '/account/deletion', json={'email': 'user-a@example.com', 'confirmation': 'DELETE'})
                self.assertEqual(response.status_code, 409, response.text)
            finally:
                finish.set()
                await task

    async def test_identity_delete_retries_failures_and_only_targets_verified_id(self):
        from app.services.account_deletion import delete_identity
        self.enable_deletion()
        with patch('httpx.AsyncClient.request', new=AsyncMock(return_value=Response(200))) as request:
            await delete_identity(USER_A)
            self.assertEqual(request.call_args.args, ('DELETE', 'https://auth.test/auth/v1/admin/users/' + USER_A))
            self.assertEqual(request.call_args.kwargs['json'], {'should_soft_delete': False})
        with patch('httpx.AsyncClient.request', new=AsyncMock(return_value=Response(503))):
            with self.assertRaises(RuntimeError):
                await delete_identity(USER_A)

    async def test_api_workflow(self):
        self.assertEqual((await self.client.get('/health')).status_code, 200)
        repo_id = await self.upload()
        status = (await self.client.get(f'/repositories/{repo_id}/status')).json()
        self.assertEqual(status['status'], 'READY', status)
        self.assertEqual(status['total_files'], 2)
        self.assertGreater(status['total_chunks'], 0)
        for route in (f'/repositories/{repo_id}', f'/repositories/{repo_id}/stats', f'/symbols/{repo_id}'):
            response = await self.client.get(route)
            self.assertEqual(response.status_code, 200, response.text)
        files = (await self.client.get(f'/repositories/{repo_id}/files')).json()
        file_id = next(f['id'] for f in files if f['path'] == 'sample.py')
        response = await self.client.get(f'/repositories/{repo_id}/files/{file_id}/content')
        self.assertEqual(response.json()['content'], SOURCE)
        result = await self.client.post('/search', json={'repository_id': repo_id, 'query': 'add two numbers'})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertGreater(result.json()['total_results'], 0)
        response = await self.client.post(f'/analysis/{repo_id}')
        self.assertEqual(response.status_code, 200, response.text)
        issues = (await self.client.get(f'/analysis/{repo_id}/issues')).json()
        self.assertTrue(any(i['issue_type'] == 'UNSAFE_EVAL' for i in issues), issues)
        for streaming in (False, True):
            response = await self.client.post('/chat', json={'repository_id': repo_id, 'question': 'What does add do?', 'stream': streaming})
            self.assertEqual(response.status_code, 200, response.text)
            if streaming:
                self.assertIn('"type": "done"', response.text)
            else:
                self.assertGreater(len(response.json()['sources']), 0)
        for route, payload in (
            ('/generate/tests', {'repository_id': repo_id, 'file_id': file_id}),
            ('/generate/docs', {'repository_id': repo_id, 'doc_type': 'readme'}),
        ):
            response = await self.client.post(route, json=payload)
            self.assertEqual(response.status_code, 200, response.text)
        response = await self.client.post(f'/repositories/{repo_id}/reindex')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(vector_store.get_chunk_count(repo_id), status['total_chunks'])

    async def test_rate_limits_follow_verified_accounts_and_include_retry_headers(self):
        from app.guards import account_limiter, edge_limiter
        account_limiter.windows.clear(); edge_limiter.windows.clear()
        with patch.object(settings, 'RESOURCE_GUARDS_ENABLED', True):
            for _ in range(10):
                result = await self.client.post('/chat', json={'repository_id': 'missing', 'question': 'test'})
                self.assertEqual(result.status_code, 404)
            limited = await self.client.post('/chat', json={'repository_id': 'missing', 'question': 'test'},
                headers={'X-Forwarded-For': '1.2.3.4', 'Origin': settings.FRONTEND_URL})
            self.assertEqual(limited.status_code, 429)
            self.assertGreater(int(limited.headers['Retry-After']), 0)
            self.assertEqual(limited.headers['access-control-allow-origin'], settings.FRONTEND_URL)
            other = await self.client.post('/chat', json={'repository_id': 'missing', 'question': 'test'},
                headers={'Authorization': 'Bearer user-b'})
            self.assertEqual(other.status_code, 404)
            self.assertEqual((await self.client.get('/health')).status_code, 200)
        account_limiter.windows.clear(); edge_limiter.windows.clear()

    async def test_request_body_limit_handles_declared_and_chunked_bodies(self):
        from app.guards import edge_limiter
        edge_limiter.windows.clear()
        with patch.object(settings, 'RESOURCE_GUARDS_ENABLED', True):
            oversized = await self.client.post('/search', content=b'x' * (300 * 1024), headers={'Content-Type': 'application/json'})
            self.assertEqual(oversized.status_code, 413)
            async def chunks():
                yield b'{"query":"'
                yield b'x' * (300 * 1024)
                yield b'"}'
            chunked = await self.client.post('/search', content=chunks(), headers={'Content-Type': 'application/json'})
            self.assertEqual(chunked.status_code, 413)

    async def test_limiter_expiry_and_memory_cap(self):
        from app.guards import WindowLimiter
        limiter = WindowLimiter(max_keys=2)
        self.assertEqual(limiter.check('a', 2, 60, now=0), 0)
        self.assertEqual(limiter.check('a', 2, 60, now=1), 0)
        self.assertEqual(limiter.check('a', 2, 60, now=2), 58)
        self.assertEqual(limiter.check('b', 2, 60, now=2), 0)
        self.assertGreater(limiter.check('c', 2, 60, now=2), 0)
        self.assertEqual(limiter.check('a', 2, 60, now=60), 0)
        self.assertEqual(limiter.check('c', 2, 60, now=200), 0)
        self.assertLessEqual(len(limiter.windows), 2)

    async def test_archives_reject_traversal_symlinks_and_expansion_before_extracting(self):
        from app.services.archive_safety import extract_safe
        import stat
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for kind in ('traversal', 'symlink', 'large', 'many'):
                zip_path = root / (kind + '.zip')
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                    if kind == 'traversal':
                        z.writestr('../outside.txt', 'unsafe')
                    elif kind == 'symlink':
                        entry = zipfile.ZipInfo('link')
                        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                        z.writestr(entry, '/etc/passwd')
                    elif kind == 'large':
                        z.writestr('large.txt', b'x' * (2 * 1024 * 1024))
                    else:
                        z.writestr('a', '1'); z.writestr('b', '2')
                with patch.object(settings, 'MAX_EXTRACTED_SIZE_MB', 1), patch.object(settings, 'MAX_REPOSITORY_FILES', 1):
                    with self.assertRaises(ValueError):
                        extract_safe(zip_path, root / kind)
                self.assertEqual(list((root / kind).rglob('*')), [])
            self.assertFalse((root / 'outside.txt').exists())
            safe = root / 'safe.zip'
            safe.write_bytes(archive())
            extract_safe(safe, root / 'safe')
            self.assertEqual((root / 'safe/sample.py').read_text(), SOURCE)

    async def test_queue_limit_preserves_duplicate_reuse(self):
        from app.services.admission_service import admit
        from fastapi import HTTPException
        with patch.object(settings, 'RESOURCE_GUARDS_ENABLED', True):
            async with AsyncSessionLocal() as db:
                first, _ = await admit(db, USER_A, 'one', 'zip', 'one', 'one')
                await admit(db, USER_A, 'two', 'zip', 'two', 'two')
                with self.assertRaises(HTTPException) as exc:
                    await admit(db, USER_A, 'three', 'zip', 'three', 'three')
                self.assertEqual(exc.exception.status_code, 429)
                cached, reused = await admit(db, USER_A, 'one', 'zip', 'one', 'one')
                self.assertTrue(reused)
                self.assertEqual(cached.id, first.id)

    async def test_ready_fails_without_storage_and_model_slots_release_after_errors(self):
        self.assertEqual((await self.client.get('/ready')).status_code, 200)
        with patch('app.services.archive_safety.ensure_disk_space', side_effect=ValueError('full')):
            self.assertEqual((await self.client.get('/ready')).status_code, 503)
        from app.services.llm.groq_provider import model_slot
        from types import SimpleNamespace
        provider = SimpleNamespace(slots=asyncio.Semaphore(2))
        with self.assertRaises(ValueError):
            async with model_slot(provider):
                raise ValueError('provider failed')
        async with model_slot(provider):
            async with model_slot(provider):
                self.assertTrue(provider.slots.locked())

    async def test_lifetime_quota_cache_and_deletion(self):
        payload = archive()
        async def submit(data=payload):
            return await self.client.post('/repositories/upload', files={'file': ('sample.zip', data, 'application/zip')})
        first = await submit()
        repo_id = first.json()['id']
        second = await submit()
        self.assertTrue(second.json()['reused'])
        self.assertEqual(second.json()['id'], repo_id)
        self.assertEqual((await self.client.get('/repositories/usage')).json()['used'], 1)
        for number in range(9):
            self.assertEqual((await submit(payload + str(number).encode())).status_code, 200)
        blocked = await submit(payload + b'eleventh')
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()['detail']['code'], 'analysis_limit')
        self.assertTrue((await submit()).json()['reused'])
        from app.models.summary import RepositorySummary
        async with AsyncSessionLocal() as db:
            db.add(RepositorySummary(id='quota-summary', repository_id=repo_id,
                                     summary_type='repository', content='Saved summary'))
            await db.commit()
        self.assertEqual((await self.client.delete(f'/repositories/{repo_id}')).status_code, 200)
        async with AsyncSessionLocal() as db:
            self.assertIsNone(await db.get(RepositorySummary, 'quota-summary'))
        self.assertEqual((await submit()).status_code, 409)
        self.assertEqual((await self.client.get('/repositories/usage')).json()['used'], 10)
        self.client.headers['Authorization'] = 'Bearer user-b'
        own = await submit()
        self.assertEqual(own.status_code, 200)
        self.assertNotEqual(own.json()['id'], repo_id)
        self.assertFalse(own.json()['reused'])
        self.assertEqual((await self.client.get('/repositories/usage')).json()['used'], 1)

    async def test_failed_import_and_restart_release_reservations(self):
        with patch.object(embedding_service, 'embed_batch', side_effect=RuntimeError('failure')):
            await self.upload()
        self.assertEqual((await self.client.get('/repositories/usage')).json(), dict(limit=10, used=0, reserved=0, remaining=10))
        with patch('app.api.routes.repository.run_zip_ingestion', new=AsyncMock()):
            repo_id = await self.upload()
        self.assertEqual((await self.client.get('/repositories/usage')).json()['reserved'], 1)
        self.assertEqual((await self.client.delete(f'/repositories/{repo_id}')).status_code, 409)
        await recover_interrupted_jobs()
        self.assertEqual((await self.client.get('/repositories/usage')).json()['remaining'], 10)
        self.assertEqual((await self.client.get(f'/repositories/{repo_id}')).json()['status'], 'FAILED')

    async def test_parallel_admissions_cannot_exceed_limit_or_duplicate_cache(self):
        from app.services.admission_service import admit, usage
        from fastapi import HTTPException
        async def request(key):
            async with AsyncSessionLocal() as db:
                try:
                    repo, reused = await admit(db, USER_A, 'parallel', 'zip', key, key)
                    return repo.id, reused
                except HTTPException as exc:
                    return exc.status_code, False
        duplicates = await asyncio.gather(*(request('same') for _ in range(5)))
        self.assertEqual(len({item[0] for item in duplicates}), 1)
        self.assertEqual(sum(not item[1] for item in duplicates), 1)
        results = await asyncio.gather(*(request(str(n)) for n in range(12)))
        self.assertEqual(sum(item[0] == 409 for item in results), 3)
        async with AsyncSessionLocal() as db:
            self.assertEqual((await usage(db, USER_A))['reserved'], 10)

    async def test_github_cache_requires_new_revision_confirmation(self):
        from app.services.admission_service import normalize_url
        self.assertEqual(normalize_url('https://GitHub.com/Example/Project.git/'), 'https://github.com/example/project')
        url = 'https://github.com/example/project'
        with patch('app.api.routes.repository.resolve_revision', new=AsyncMock(return_value='a' * 40)), patch('app.api.routes.repository.run_github_ingestion', new=AsyncMock()) as worker:
            first = await self.client.post('/repositories/github', json={'url': url})
            cached = await self.client.post('/repositories/github', json={'url': url + '.git'})
            self.assertEqual(first.json()['id'], cached.json()['id'])
            self.assertTrue(cached.json()['reused'])
            worker.assert_awaited_once_with(first.json()['id'], url, 'a' * 40)
        async with AsyncSessionLocal() as db:
            await service.update_repository_status(db, first.json()['id'], 'READY')
        with patch('app.api.routes.repository.resolve_revision', new=AsyncMock(return_value='b' * 40)), patch('app.api.routes.repository.run_github_ingestion', new=AsyncMock()):
            prompt = await self.client.post('/repositories/github', json={'url': url})
            self.assertEqual(prompt.status_code, 409)
            self.assertEqual(prompt.json()['detail']['code'], 'revision_confirmation')
            stale = await self.client.post('/repositories/github', json={'url': url, 'confirmed_revision': 'a' * 40})
            self.assertEqual(stale.status_code, 409)
            confirmed = await self.client.post('/repositories/github', json={'url': url, 'confirmed_revision': 'b' * 40})
            self.assertEqual(confirmed.status_code, 200)
            self.assertNotEqual(confirmed.json()['id'], first.json()['id'])
        counts = (await self.client.get('/repositories/usage')).json()
        self.assertEqual((counts['used'], counts['reserved']), (1, 1))

    async def test_analysis_lifecycle_and_atomic_rescan(self):
        repo_id = await self.upload()
        path = f'/analysis/{repo_id}'
        initial = (await self.client.get(path + '/summary')).json()
        self.assertEqual(initial['analysis_status'], 'NOT_RUN')
        self.assertIsNone(initial['health_score'])
        await self.client.post(path)
        scanned = (await self.client.get(path + '/summary')).json()
        self.assertEqual(scanned['analysis_status'], 'COMPLETED')
        self.assertEqual(scanned['coverage']['scanned_files'], 2)
        self.assertLessEqual(scanned['health_score'], 49)  # eval finding
        original = (await self.client.get(path + '/issues')).json()
        await self.client.post(path)
        self.assertEqual(len((await self.client.get(path + '/issues')).json()), len(original))
        with patch('app.services.analyzer.analysis_engine._scan_files', side_effect=OSError('Missing file')):
            await self.client.post(path + '?force=true')
        failed = (await self.client.get(path + '/summary')).json()
        self.assertEqual(failed['analysis_status'], 'FAILED')
        self.assertEqual(failed['health_score'], scanned['health_score'])
        self.assertEqual(len((await self.client.get(path + '/issues')).json()), len(original))
        await self.client.post(path)
        self.assertEqual((await self.client.get(path + '/summary')).json()['analysis_status'], 'COMPLETED')

    async def test_chat_history_survives_restart_and_supports_management(self):
        repo_id = await self.upload()
        first = (await self.client.post('/chat', json={'repository_id': repo_id, 'question': 'First question'})).json()
        conv_id = first['conversation_id']
        second = await self.client.post('/chat', json={
            'repository_id': repo_id, 'conversation_id': conv_id, 'question': 'Follow up', 'stream': True,
        })
        self.assertIn('"type": "done"', second.text)
        # Dispose connections and initialize again: all history is in the database.
        await engine.dispose()
        await init_db()
        history = (await self.client.get(f'/chat/history/{conv_id}')).json()
        self.assertEqual([m['role'] for m in history], ['user', 'assistant', 'user', 'assistant'])
        self.assertEqual(history[0]['content'], 'First question')
        self.assertEqual(history[1]['sources'], first['sources'])
        self.assertTrue(history[3]['sources'])
        renamed = await self.client.patch(f'/chat/conversations/{conv_id}', json={'title': ' Architecture notes '})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(renamed.json()['title'], 'Architecture notes')
        listing = (await self.client.get(f'/chat/conversations/{repo_id}')).json()
        self.assertEqual(listing[0]['title'], 'Architecture notes')
        self.assertFalse(listing[0]['is_generating'])
        self.assertEqual((await self.client.patch(f'/chat/conversations/{conv_id}', json={'title': ' '})).status_code, 422)
        self.assertEqual((await self.client.delete(f'/chat/conversations/{conv_id}')).status_code, 204)
        self.assertEqual((await self.client.get(f'/chat/history/{conv_id}')).status_code, 404)
        self.assertEqual((await self.client.get(f'/chat/conversations/{repo_id}')).json(), [])
        from app.models.conversation import Message
        from app.models.repository import RepositoryJob
        async with AsyncSessionLocal() as db:
            self.assertIsNone(await db.scalar(select(Message.id).where(Message.conversation_id == conv_id)))
            self.assertIsNone(await db.scalar(select(RepositoryJob.id).where(RepositoryJob.job_type == f'CHAT:{conv_id}')))
        self.assertEqual((await self.client.get(f'/repositories/{repo_id}')).status_code, 200)

    async def test_chat_failure_preserves_question_without_saving_partial_reply(self):
        repo_id = await self.upload()
        async def failing_stream(**kwargs):
            yield 'partial reply', []
            raise RuntimeError('Simulated provider outage')
        with patch('app.api.routes.chat.stream_question', new=failing_stream):
            result = await self.client.post('/chat', json={'repository_id': repo_id, 'question': 'Keep this question', 'stream': True})
        self.assertIn('"type": "error"', result.text)
        self.assertNotIn('"type": "done"', result.text)
        listing = (await self.client.get(f'/chat/conversations/{repo_id}')).json()
        self.assertFalse(listing[0]['is_generating'])
        conv_id = listing[0]['id']
        history = (await self.client.get(f'/chat/history/{conv_id}')).json()
        self.assertEqual([(m['role'], m['content']) for m in history], [('user', 'Keep this question')])
        with patch('app.api.routes.chat.ask_question', new=AsyncMock(side_effect=RuntimeError('Provider outage'))):
            result = await self.client.post('/chat', json={'repository_id': repo_id, 'conversation_id': conv_id, 'question': 'Keep this too'})
        self.assertEqual(result.status_code, 502)
        history = (await self.client.get(f'/chat/history/{conv_id}')).json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1]['content'], 'Keep this too')

    async def test_chat_disconnect_and_busy_conversation(self):
        from app.api.routes.chat import chat
        from app.schemas.chat import ChatRequest
        from app.auth import AuthUser
        repo_id = await self.upload()
        # Close the stream at the first metadata event, before the model is called.
        async with AsyncSessionLocal() as db:
            response = await chat(ChatRequest(repository_id=repo_id, question='Interrupted question', stream=True),
                                  db=db, user=AuthUser(id=USER_A, email='user-a@example.com'))
            await anext(response.body_iterator)
            listing = (await self.client.get(f'/chat/conversations/{repo_id}')).json()
            conv_id = listing[0]['id']
            self.assertTrue(listing[0]['is_generating'])
            self.assertEqual((await self.client.delete(f'/chat/conversations/{conv_id}')).status_code, 409)
            self.assertEqual((await self.client.post('/chat', json={
                'repository_id': repo_id, 'conversation_id': conv_id, 'question': 'Concurrent question',
            })).status_code, 409)
            await response.body_iterator.aclose()
        self.assertFalse((await self.client.get(f'/chat/conversations/{repo_id}')).json()[0]['is_generating'])
        self.assertEqual(len((await self.client.get(f'/chat/history/{conv_id}')).json()), 1)

    async def test_chat_restart_releases_interrupted_reply(self):
        from app.models.repository import RepositoryJob
        repo_id = await self.upload()
        result = (await self.client.post('/chat', json={'repository_id': repo_id, 'question': 'Persist me'})).json()
        conv_id = result['conversation_id']
        async with AsyncSessionLocal() as db:
            db.add(RepositoryJob(id='chat-restart-' + conv_id, repository_id=repo_id,
                                 job_type=f'CHAT:{conv_id}', status='RUNNING'))
            await db.commit()
        await recover_interrupted_jobs()
        self.assertFalse((await self.client.get(f'/chat/conversations/{repo_id}')).json()[0]['is_generating'])
        self.assertEqual(len((await self.client.get(f'/chat/history/{conv_id}')).json()), 2)

    async def test_analysis_clean_and_unsupported_coverage(self):
        from app.models.repository import File
        from sqlalchemy import update
        response = await self.client.post('/repositories/upload', files={
            'file': ('clean.zip', archive('def add(a, b):\n    return a + b\n'), 'application/zip'),
        })
        repo_id = response.json()['id']
        path = f'/analysis/{repo_id}'
        await self.client.post(path)
        clean = (await self.client.get(path + '/summary')).json()
        self.assertEqual(clean['health_score'], 100)
        self.assertEqual(clean['total_issues'], 0)
        async with AsyncSessionLocal() as db:
            await db.execute(update(File).where(File.repository_id == repo_id).values(language='markdown'))
            await db.commit()
        await self.client.post(path)
        unsupported = (await self.client.get(path + '/summary')).json()
        self.assertIsNone(unsupported['health_score'])
        self.assertEqual(unsupported['coverage']['scanned_files'], 0)

    async def test_analysis_density_and_severity_caps(self):
        from app.services.analyzer.analysis_engine import calculate_health_score
        score = calculate_health_score({'LOW': 70}, 3833)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)
        self.assertEqual(calculate_health_score({'LOW': 20}, 1000),
                         calculate_health_score({'LOW': 40}, 2000))
        self.assertLess(calculate_health_score({'HIGH': 20}, 1000),
                        calculate_health_score({'LOW': 20}, 1000))
        self.assertLessEqual(calculate_health_score({'CRITICAL': 1}, 100000), 49)
        self.assertLessEqual(calculate_health_score({'HIGH': 1}, 100000), 79)

    async def test_analysis_running_duplicate_and_restart(self):
        from app.models.repository import RepositoryJob
        repo_id = await self.upload()
        async with AsyncSessionLocal() as db:
            job = RepositoryJob(id='analysis-' + repo_id, repository_id=repo_id,
                                job_type='ANALYSIS', status='RUNNING')
            db.add(job)
            await db.commit()
        response = await self.client.post(f'/analysis/{repo_id}')
        self.assertEqual(response.json()['job_id'], job.id)
        await recover_interrupted_jobs()
        summary = (await self.client.get(f'/analysis/{repo_id}/summary')).json()
        self.assertEqual(summary['analysis_status'], 'FAILED')
        self.assertIsNone(summary['health_score'])

    async def test_health_remains_responsive_during_embeddings(self):
        entered = asyncio.Event()
        loop = asyncio.get_running_loop()
        started = []

        def slow_embedding(texts):
            started.append(time.monotonic())
            loop.call_soon_threadsafe(entered.set)
            time.sleep(0.4)
            return [[1.0] + [0.0] * 383 for _ in texts]

        with patch.object(embedding_service, 'embed_batch', side_effect=slow_embedding):
            task = asyncio.create_task(self.upload())
            await asyncio.wait_for(entered.wait(), timeout=10)
            # If inference blocks the event loop, this request cannot run until it ends.
            elapsed = time.monotonic() - started[0]
            response = await self.client.get('/health')
            await task
        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed, 0.35, f'Event loop blocked for {elapsed:.3f}s')
        print(f'Event loop resumed during inference in {elapsed:.4f}s')

    async def test_vector_batches_keep_text_and_metadata_aligned(self):
        batches = []

        def embed(texts):
            batches.append(texts)
            return [[float(len(text))] + [0.0] * 383 for text in texts]

        def store(**kwargs):
            texts = batches[-1]
            self.assertLessEqual(len(texts), 2)
            for text, document, embedding, metadata in zip(texts, kwargs['documents'], kwargs['embeddings'], kwargs['metadatas']):
                self.assertTrue(text.endswith(document))
                self.assertIn(metadata['file_path'], text)
                self.assertEqual(embedding[0], len(text))

        with patch.object(settings, 'EMBEDDING_WRITE_BATCH_SIZE', 2), patch.object(embedding_service, 'embed_batch', side_effect=embed), patch.object(vector_store, 'add_chunks', side_effect=store):
            repo_id = await self.upload()
        self.assertGreater(len(batches), 1)
        self.assertEqual((await self.client.get(f'/repositories/{repo_id}/status')).json()['status'], 'READY')

    async def test_restart_recovers_only_interrupted_repositories(self):
        async with AsyncSessionLocal() as db:
            ready = await service.create_repository(db, 'finished', 'zip', owner_id=USER_A)
            await service.update_repository_status(db, ready.id, 'READY')
            interrupted = await service.create_repository(db, 'interrupted', 'zip', owner_id=USER_A)
            await service.update_repository_status(db, interrupted.id, 'ANALYZING')
            ready_id, interrupted_id = ready.id, interrupted.id
        await recover_interrupted_jobs()
        self.assertEqual((await self.client.get(f'/repositories/{ready_id}/status')).json()['status'], 'READY')
        status = (await self.client.get(f'/repositories/{interrupted_id}/status')).json()
        self.assertEqual(status['status'], 'FAILED')
        self.assertIn('restart', status['error_message'])

    async def test_failed_transaction_can_save_failed_status(self):
        async def fail_transaction(db, repo_id, directory):
            db.add(Repository(id=repo_id, name='duplicate', source_type='zip'))
            await db.flush()
        with patch.object(service, 'index_directory', side_effect=fail_transaction):
            repo_id = await self.upload()
        self.assertEqual((await self.client.get(f'/repositories/{repo_id}/status')).json()['status'], 'FAILED')

    async def test_embedding_error_is_terminal(self):
        with patch.object(embedding_service, 'embed_batch', side_effect=RuntimeError('Simulated embedding failure')):
            repo_id = await self.upload()
        status = (await self.client.get(f'/repositories/{repo_id}/status')).json()
        self.assertEqual(status['status'], 'FAILED')
        self.assertIn('Simulated embedding failure', status['error_message'])

    async def test_invalid_zip_is_terminal(self):
        response = await self.client.post('/repositories/upload', files={'file': ('bad.zip', b'not a zip', 'application/zip')})
        self.assertEqual(response.status_code, 200)
        repo_id = response.json()['id']
        status = (await self.client.get(f'/repositories/{repo_id}/status')).json()
        self.assertEqual(status['status'], 'FAILED')

    async def test_websocket_and_app_lifespan(self):
        from fastapi.testclient import TestClient
        repo_id = await self.upload()

        def check_socket():
            with TestClient(app) as client:
                self.assertEqual(client.get('/health').status_code, 200)
                with client.websocket_connect(f'/ws/progress/{repo_id}', headers={'origin': settings.FRONTEND_URL}) as ws:
                    ws.send_json({'type': 'authenticate', 'access_token': 'user-a'})
                    self.assertEqual(ws.receive_json()['status'], 'READY')

        await asyncio.to_thread(check_socket)

    async def test_authentication_fails_closed(self):
        for header, expected in (('', 401), ('Basic abc', 401), ('Bearer forged', 401), ('Bearer unavailable', 503)):
            response = await self.client.get('/repositories', headers={'Authorization': header})
            self.assertEqual(response.status_code, expected, response.text)
        with patch.object(settings, 'SUPABASE_PUBLISHABLE_KEY', ''):
            self.assertEqual((await self.client.get('/account/me')).status_code, 503)
        for payload, expected in (
            ({'id': 'invalid', 'email': 'test@example.com'}, 401),
            ({'id': USER_A, 'email': 'test@example.com'}, 403),
            ({'id': USER_A, 'email': 'test@example.com', 'email_confirmed_at': 'now', 'is_anonymous': True}, 403),
        ):
            with patch.object(auth, '_fetch_user', new=AsyncMock(return_value=Response(200, json=payload))):
                self.assertEqual((await self.client.get('/account/me')).status_code, expected)
        self.assertEqual((await self.client.get('/account/me')).json()['id'], USER_A)

    async def test_all_data_routes_require_auth(self):
        from fastapi.routing import APIRoute
        from app.auth import get_current_user
        def guarded(dependency):
            return dependency.call is get_current_user or any(guarded(d) for d in dependency.dependencies)
        for route in app.routes:
            if isinstance(route, APIRoute) and route.path not in ('/', '/health', '/ready'):
                self.assertTrue(guarded(route.dependant), route.path)

    async def test_cross_account_and_legacy_isolation(self):
        repo_id = await self.upload()
        file_id = (await self.client.get(f'/repositories/{repo_id}/files')).json()[0]['id']
        chat = await self.client.post('/chat', json={'repository_id': repo_id, 'question': 'Explain this'})
        conversation_id = chat.json()['conversation_id']
        async with AsyncSessionLocal() as db:
            legacy = Repository(id='legacy-unowned', name='Legacy', source_type='zip', status='READY')
            db.add(legacy)
            await db.commit()
        for token in ('user-a', 'user-b'):
            self.assertEqual((await self.client.get('/repositories/legacy-unowned', headers={'Authorization': f'Bearer {token}'})).status_code, 404)
        self.client.headers['Authorization'] = 'Bearer user-b'
        self.assertEqual((await self.client.patch(f'/chat/conversations/{conversation_id}', json={'title': 'Not yours'})).status_code, 404)
        self.assertEqual((await self.client.delete(f'/chat/conversations/{conversation_id}')).status_code, 404)
        listed = (await self.client.get('/repositories')).json()
        self.assertNotIn(repo_id, [r['id'] for r in listed])
        self.assertNotIn('legacy-unowned', [r['id'] for r in listed])
        for route in (
            f'/repositories/{repo_id}', f'/repositories/{repo_id}/status',
            f'/repositories/{repo_id}/files', f'/repositories/{repo_id}/stats',
            f'/repositories/{repo_id}/files/{file_id}/content',
            f'/symbols/{repo_id}', f'/symbols/file/{file_id}',
            f'/summary/file/{file_id}', f'/summary/repository/{repo_id}', f'/summary/files/{repo_id}',
            f'/analysis/{repo_id}/issues', f'/analysis/{repo_id}/summary',
            f'/chat/conversations/{repo_id}', f'/chat/history/{conversation_id}',
            f'/generate/symbols/{repo_id}/{file_id}',
        ):
            result = await self.client.get(route)
            self.assertEqual(result.status_code, 404, (route, result.text))
        for route, payload in (
            ('/search', {'repository_id': repo_id, 'query': 'test'}),
            ('/chat', {'repository_id': repo_id, 'question': 'test'}),
            ('/chat', {'repository_id': repo_id, 'question': 'test', 'stream': True}),
            ('/generate/tests', {'repository_id': repo_id, 'file_id': file_id}),
            ('/generate/docs', {'repository_id': repo_id, 'doc_type': 'readme'}),
            (f'/analysis/{repo_id}', {}), (f'/repositories/{repo_id}/reindex', {}),
        ):
            result = await self.client.post(route, json=payload)
            self.assertEqual(result.status_code, 404, (route, result.text))
        self.assertEqual((await self.client.delete(f'/repositories/{repo_id}')).status_code, 404)
        own_repo = await self.upload()
        self.assertEqual((await self.client.get(f'/repositories/{own_repo}')).status_code, 200)
        # Supplying an owned repo with somebody else's file or conversation must also fail.
        for route, payload in (
            ('/generate/tests', {'repository_id': own_repo, 'file_id': file_id}),
            ('/chat', {'repository_id': own_repo, 'conversation_id': conversation_id, 'question': 'test'}),
        ):
            self.assertEqual((await self.client.post(route, json=payload)).status_code, 404)
        self.client.headers['Authorization'] = 'Bearer user-a'
        second_repo = await self.upload()
        self.assertEqual((await self.client.post('/chat', json={
            'repository_id': second_repo, 'conversation_id': conversation_id, 'question': 'test',
        })).status_code, 404)
        self.assertEqual((await self.client.get(f'/repositories/{repo_id}')).status_code, 200)

    async def test_websocket_refuses_other_users_and_missing_auth(self):
        from fastapi.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect
        repo_id = await self.upload()
        def check_socket():
            with TestClient(app) as client:
                for token, expected in (('user-b', 4404), ('forged', 4401), (None, 4401)):
                    with client.websocket_connect(f'/ws/progress/{repo_id}', headers={'origin': settings.FRONTEND_URL}) as ws:
                        ws.send_json({'type': 'authenticate', 'access_token': token})
                        with self.assertRaises(WebSocketDisconnect) as exc:
                            ws.receive_json()
                        self.assertEqual(exc.exception.code, expected)
                with self.assertRaises(WebSocketDisconnect) as exc:
                    with client.websocket_connect(f'/ws/progress/{repo_id}', headers={'origin': 'https://untrusted.test'}):
                        pass
                self.assertEqual(exc.exception.code, 1008)
        await asyncio.to_thread(check_socket)

    async def test_ingestion_rejects_untrusted_clone_hosts(self):
        for url in ('https://github.com.evil.test/a/b', 'file:///tmp/github.com/repo',
                    'https://github.com@evil.test/a/b', 'http://github.com/a/b',
                    'https://github.com:8443/a/b'):
            response = await self.client.post('/repositories/github', json={'url': url})
            self.assertEqual(response.status_code, 400, url)
        with patch('app.api.routes.repository.run_github_ingestion', new=AsyncMock()) as worker, patch('app.api.routes.repository.resolve_revision', new=AsyncMock(return_value='a' * 40)):
            response = await self.client.post('/repositories/github', json={
                'url': 'https://github.com/example/project', 'owner_id': USER_B,
            })
            self.assertEqual(response.status_code, 200, response.text)
            async with AsyncSessionLocal() as db:
                repo = await db.get(Repository, response.json()['id'])
                self.assertEqual(repo.owner_id, USER_A)
            worker.assert_awaited_once()

    async def test_owned_file_cannot_escape_repository_directory(self):
        from app.models.repository import File
        repo_id = await self.upload()
        file_id = (await self.client.get(f'/repositories/{repo_id}/files')).json()[0]['id']
        outside = Path(scratch.name) / 'outside.py'
        outside.write_text('private content')
        async with AsyncSessionLocal() as db:
            file = await db.get(File, file_id)
            file.path = str(outside)
            await db.commit()
        response = await self.client.get(f'/repositories/{repo_id}/files/{file_id}/content')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('private content', response.text)

    @unittest.skipUnless(args.project_fixture, 'Enable --project-fixture to index first-party source')
    async def test_project_source_ingestion(self):
        # Explicit source-only allowlist: excludes dotenv, Git, dependencies and user data.
        paths = [ROOT / 'backend/main.py']
        paths += sorted((ROOT / 'backend/app').rglob('*.py'))
        paths += sorted((ROOT / 'frontend/src').rglob('*.ts'))
        paths += sorted((ROOT / 'frontend/src').rglob('*.tsx'))
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as zf:
            for path in paths:
                zf.writestr(path.relative_to(ROOT).as_posix(), path.read_bytes())
        started = time.monotonic()
        response = await self.client.post('/repositories/upload', files={'file': ('project.zip', data.getvalue(), 'application/zip')})
        self.assertEqual(response.status_code, 200, response.text)
        repo_id = response.json()['id']
        status = (await self.client.get(f'/repositories/{repo_id}/status')).json()
        self.assertEqual(status['status'], 'READY', status)
        self.assertEqual(status['total_files'], len(paths))
        self.assertEqual(vector_store.get_chunk_count(repo_id), status['total_chunks'])
        result = await self.client.post('/search', json={'repository_id': repo_id, 'query': 'embed code chunks and store vectors'})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertGreater(result.json()['total_results'], 0)
        print(f'Project fixture: {len(paths)} files, {status["total_chunks"]} chunks, {time.monotonic() - started:.2f}s')


if __name__ == '__main__':
    print(f'Mode: {"real cached model" if args.real_model else "mock embeddings"}; GPU requested: {args.gpu}; LLM mocked; isolated SQLite and Chroma')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BackendChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # Chroma holds file handles on Windows; the OS temp directory is intentionally isolated.
    os.chdir(ROOT)
    try:
        scratch.cleanup()
    except PermissionError:
        pass
    sys.exit(0 if result.wasSuccessful() else 1)
