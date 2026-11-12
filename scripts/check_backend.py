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
        await init_db()
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
        response = await self.client.post('/repositories/upload', files={'file': ('sample.zip', archive(), 'application/zip')})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['id']

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
            await self.client.post(path)
        failed = (await self.client.get(path + '/summary')).json()
        self.assertEqual(failed['analysis_status'], 'FAILED')
        self.assertEqual(failed['health_score'], scanned['health_score'])
        self.assertEqual(len((await self.client.get(path + '/issues')).json()), len(original))
        await self.client.post(path)
        self.assertEqual((await self.client.get(path + '/summary')).json()['analysis_status'], 'COMPLETED')

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
            if isinstance(route, APIRoute) and route.path not in ('/', '/health'):
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
        with patch('app.api.routes.repository.run_github_ingestion', new=AsyncMock()) as worker:
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
