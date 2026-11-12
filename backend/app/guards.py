"""Bounded, in-process protections for the supported single-worker deployment."""
import math
import time
from collections import OrderedDict, deque
from fastapi import HTTPException
from starlette.responses import JSONResponse
from app.config.settings import settings


class WindowLimiter:
    def __init__(self, max_keys=4096):
        self.windows = OrderedDict()
        self.max_keys = max_keys

    def check(self, key, limit, seconds, now=None):
        now = time.monotonic() if now is None else now
        # Drop inactive entries, never evict an active allowance to grant more requests.
        for old_key, (expires, _) in list(self.windows.items()):
            if expires <= now:
                del self.windows[old_key]
        if key not in self.windows:
            if len(self.windows) >= self.max_keys:
                return 60
            self.windows[key] = (now + seconds, deque())
        _, entries = self.windows[key]
        while entries and entries[0] <= now - seconds:
            entries.popleft()
        if len(entries) >= limit:
            return max(1, math.ceil(entries[0] + seconds - now))
        entries.append(now)
        self.windows[key] = (now + seconds, entries)
        return 0


account_limiter = WindowLimiter()
edge_limiter = WindowLimiter(max_keys=4)


def limited(retry):
    raise HTTPException(429, f'Too many requests. Please try again in {retry} seconds.',
                        headers={'Retry-After': str(retry)})


def check_account(user_id, method, path):
    if not settings.RESOURCE_GUARDS_ENABLED:
        return
    retry = account_limiter.check((user_id, 'all'), 240, 60)
    if retry:
        limited(retry)
    ai = path == '/chat' or (method == 'POST' and path.startswith('/generate/')) or path.startswith(('/summary/file/', '/summary/repository/'))
    group = None
    if ai:
        group = ('ai', 10)
        retry = account_limiter.check((user_id, 'ai-day'), 200, 86400)
        if retry:
            limited(retry)
    elif method == 'POST' and path in ('/repositories/upload', '/repositories/github'):
        group = ('import', 5)
    elif method == 'POST' and (path.startswith('/analysis/') or path.endswith('/reindex')):
        group = ('scan', 5)
    elif path == '/search':
        group = ('search', 30)
    if group:
        retry = account_limiter.check((user_id, group[0]), group[1], 60)
        if retry:
            limited(retry)


class RequestGuards:
    def __init__(self, app):
        self.app = app
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not settings.RESOURCE_GUARDS_ENABLED:
            return await self.app(scope, receive, send)
        path, method = scope['path'], scope['method']
        if method == 'OPTIONS' or path in ('/', '/health', '/ready'):
            return await self.app(scope, receive, send)
        # Global pre-auth allowance cannot be bypassed with invented forwarded IP headers.
        retry = edge_limiter.check('global', 600, 60)
        if retry or self.active >= 24:
            return await JSONResponse({'detail': 'Server is busy. Please retry shortly.'}, 429,
                headers={'Retry-After': str(retry or 10), 'Cache-Control': 'no-store'})(scope, receive, send)
        limit = (settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1024 * 1024) if path == '/repositories/upload' else 256 * 1024
        headers = dict(scope.get('headers', []))
        try:
            declared = int(headers.get(b'content-length', b'0'))
            if declared < 0:
                raise ValueError()
        except ValueError:
            return await JSONResponse({'detail': 'Invalid content length.'}, 400)(scope, receive, send)
        if declared > limit:
            return await JSONResponse({'detail': 'Request body is too large.'}, 413)(scope, receive, send)
        seen, rejected, started = 0, False, False
        async def bounded_receive():
            nonlocal seen, rejected
            message = await receive()
            if message['type'] == 'http.request':
                seen += len(message.get('body', b''))
                if seen > limit:
                    rejected = True
                    raise HTTPException(413, 'Request body is too large.')
            return message
        async def bounded_send(message):
            nonlocal started
            if rejected:
                if not started:
                    started = True
                    await JSONResponse({'detail': 'Request body is too large.'}, 413)(scope, receive, send)
                return
            if message['type'] == 'http.response.start':
                started = True
            await send(message)
        self.active += 1
        try:
            await self.app(scope, bounded_receive, bounded_send)
        finally:
            self.active -= 1
