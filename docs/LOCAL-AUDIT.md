# Local audit and ingestion fixes — 2026-11-11

## Scope and privacy

Reviewed the README, backend modules, frontend workflows, dependency manifests,
CI workflows and deployment configuration. Built the frontend and exercised the
backend with isolated data. Project `.env*` and `.gitignore` contents were not
opened. Existing uploads, Chroma data and live Supabase data were not used in tests.
Installed dependency internals were inspected only where needed for diagnostics.
Images and screenshots are assets, not executable tests.

The remote is `https://github.com/rock917/codelens-ai.git`. A fresh fetch confirmed
that GitHub `main` matches the audited baseline, commit `d91c3bf`. The fixes are
prepared on `codex/azure-backend-fix` in the same repository. No production
deployment or default-branch merge was performed during the audit.
The existing uncommitted change moving summarization after READY was preserved.

## Findings addressed

1. **The ANALYZING stage blocked the API loop.** Model loading, embedding generation
   and Chroma writes were synchronous inside async ingestion. Parsing, cloning,
   embedding and vector IO now run through worker threads where changed. Search
   and RAG query embedding/vector IO also leave the API loop. ZIP extraction and
   portions of file preparation still run synchronously; this is not a durable
   external worker system.
2. **Repository-wide embedding buffers increased memory pressure.** Ingestion now
   reads and embeds at most 32 database chunks per write batch by default, flushes
   file records during parsing, and avoids retaining a second full chunk list.
   Full-process peak memory has not been profiled; this does not make a small
   free-tier instance sufficient for PyTorch.
3. **Vectors could be paired with the wrong chunks.** The old path embedded one
   sequence and read database rows separately with no ordering guarantee. Each new
   batch supplies its own IDs, text, documents and metadata in the same order.
4. **Interrupted ingestion remained active forever.** Startup recovery marks
   unfinished ingestion FAILED with a retry explanation. This requires one API
   worker and one backend instance; do not run it concurrently on separate hosts
   sharing the database.
5. **Failed transactions could prevent FAILED from being saved.** Both ingestion
   paths roll back before saving the error status. Background ingestion now owns
   its database session and is serialized within the process.
6. **Progress could stop after a WebSocket disconnect.** The frontend also polls
   status, handles terminal failure, cleans up timers and shows failure details.
   The ANALYZING message now describes embeddings/vector storage correctly.
7. **Container packaging included local files.** Backend and frontend Docker builds
   now use explicit source copies and allowlist build contexts. The frontend build
   uses Node 24, a lockfile install and `/api` for the Compose proxy. The local
   SQLite Docker volume now mounts a directory rather than a database filename.

The live Render failure has **not** been confirmed from its logs. Resource
exhaustion/restarts are plausible contributors, alongside the verified code
defects above. Web retrieval of the README's live URLs failed during this audit;
that alone does not establish an application outage.

## Validation

- Installed backend dependencies: `pip check` passed.
- Python 3.11.9 environment available; GPU detected as NVIDIA GeForce RTX 2050.
- Backend Python source syntax checks passed.
- Real cached `all-MiniLM-L6-v2` embeddings and real temporary Chroma/SQLite were
  exercised on CPU and CUDA. No model download was required.
- Initial seven regression/workflow tests passed on both CPU and GPU. These cover
  ZIP ingestion, file/stat/symbol endpoints, search, seeded security analysis,
  unchanged reindex, mocked chat/SSE and generation, failed inference, corrupt ZIP,
  failed SQL transaction, startup recovery, batch alignment and loop responsiveness.
- Additional final CPU checks cover actual app lifespan/WebSocket delivery and
  ingestion/search of a source-only copy of this project. **Final run: all 9 tests
  passed in 74.481 seconds.** The project fixture contained **70 source files and
  348 chunks**; ingestion plus its search check took **46.77 seconds**, with the
  model already loaded by the preceding small-fixture test. This measures the
  local laptop using CPU inference, not an Azure VM or Render performance.
- During simulated 400 ms inference, the API loop resumed before inference ended
  (about 15–16 ms in the initial CPU/GPU runs).
- TypeScript project build and Vite production build passed without loading dotenv.
  Lint exits successfully with 56 existing warnings. Vite reports a CSS import-order
  warning and a JavaScript bundle larger than 500 kB.
- The frontend package manifest agrees with its parsed lockfile.
- Azure Compose interpolation/schema validation passed using an empty explicit
  env file and dummy values. Docker images were not built/run because Docker's
  Linux daemon was unavailable.
- `git diff --check` passed.

The first isolated run was blocked by the execution sandbox's local socket
restrictions before the Python event loop could start. Approved execution outside
that sandbox allowed testing. An optional memory-report import in the extended
test was removed after its unavailable dependency failed; ingestion itself had
already reached READY. No memory measurement is claimed.

## Reproduce without private credentials

From the repository root, on Windows:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& .\backend\venv\Scripts\python.exe scripts/check_backend.py
& .\backend\venv\Scripts\python.exe scripts/check_backend.py --real-model --project-fixture
& .\backend\venv\Scripts\python.exe scripts/check_backend.py --real-model --gpu
```

The script changes into a temporary directory **before importing application
settings**, supplies a dummy Groq key and temporary SQLite/Chroma/upload paths,
and mocks Groq responses. Real-model modes require an already cached model.
Without `--real-model`, embeddings are mocked too. Temporary Chroma handles may
prevent immediate cleanup on Windows; any retained test files remain in the OS
temporary directory, separate from project data.

Frontend checks from `frontend`:

```powershell
node node_modules/typescript/bin/tsc -b
node --input-type=module -e "import {build} from 'vite'; await build({envDir:false});"
npm run lint
```

## Remaining work identified

- Real Groq responses, Supabase connectivity and production browser behavior need
  a separately authorized/configured integration check. Mocked LLM tests verify
  application flow, not answer quality, model availability or provider limits.
- Changed/deleted-file reindexing needs follow-up: deletion does not remove old
  vectors, repository aggregate counts are not refreshed, and unchanged files
  cannot repair a lost Chroma index. Only the unchanged reindex case was tested.
- Repository deletion currently removes SQL records but leaves uploaded files and
  Chroma collections. That wastes persistent disk space over time.
- Static-analysis UI waits a fixed three seconds rather than observing a durable
  job status; large analyses can display incomplete results.
- Explorer waits for an LLM summary alongside source loading. A summary error can
  prevent otherwise available source/symbol data from being shown.
- GitHub/GitLab URL validation is only a substring check, and ZIP expanded size and
  clone duration are not bounded. Address these before opening ingestion to
  untrusted public users. Authentication is currently absent, as the README states.
- Existing CI checks mostly import modules; the new isolated workflow test was
  added to Backend CI, but GitHub Actions itself has not been run from this checkout.
- README begins with an accidental shell-command prefix and says React 18, while
  the installed/package stack uses React 19. The README also overstates aspects of
  incremental indexing and nested parsing.

Azure preparation is in `docs/AZURE-MIGRATION.md`. Keep Supabase and Vercel for the
first migration. Review region, remaining student credit, quota, total price,
HTTPS endpoint, backups and secure runtime settings before provisioning.
