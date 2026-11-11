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

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from app.database.base import AsyncSessionLocal, engine, init_db, recover_interrupted_jobs
from app.models.repository import Repository
from app.services import repository_service as service
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from app.services.llm.groq_provider import groq_provider
from main import app
from app.config.settings import settings

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
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url='http://test')

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
            ready = await service.create_repository(db, 'finished', 'zip')
            await service.update_repository_status(db, ready.id, 'READY')
            interrupted = await service.create_repository(db, 'interrupted', 'zip')
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
                with client.websocket_connect(f'/ws/progress/{repo_id}') as ws:
                    self.assertEqual(ws.receive_json()['status'], 'READY')

        await asyncio.to_thread(check_socket)

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
