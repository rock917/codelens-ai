# Private result caching

Identical imports still open the account's existing repository without using a
new lifetime credit. This release also reuses parsing, embedding vectors, file
and repository summaries, and completed health scans. Chat answers are not cached.

## Behavior

- Parsing keys include source contents, path, language and pipeline version.
- Embedding keys include input text, model and embedding implementation/settings.
  Duplicate texts in one batch are embedded once; output ordering is preserved.
- Summary keys include indexed source hashes, prompt inputs, prompt/provider code
  and model. Background and on-demand summaries use the same cache. Legacy
  summaries are regenerated once because they have no version provenance.
- Health scans compare actual source contents and analyzer code with the latest
  successful scan. Failed/interrupted scans are retried, not reported as hits.
- Analysis offers **Run fresh scan**; Explorer → AI Summary offers **Refresh
  summary**. Cache hits say **Using saved results**. Force refresh preserves the
  previous result on failure. Concurrent ordinary summary requests share work.
- An explicit reindex, or importing the same revision after a pipeline upgrade,
  refreshes outdated derived indexes without another credit. Changed indexes
  invalidate health results, which become unscored until another scan completes.
  Reindexing uses stored source files; it never fetches a different Git revision.

The cache is private to a repository and its authenticated owner. It deliberately
does not share derived data across accounts or different repository records.
Authorization still runs on every request. Request rate limits are unchanged,
including for hits; they are distinct from the lifetime import allowance.

## Storage and cleanup

Disposable JSON entries live at `UPLOAD_DIR/.codelens-cache/<repository UUID>`
outside uploaded source trees. The existing Azure `/data` volume persists them
across container restarts. No Redis, new credentials or database migration is
needed. SQL remains authoritative for stored scan findings and completed jobs.

Per repository: at most 2,000 JSON entries / 64 MiB, at most 4 MiB per entry.
Entries expire after 30 days and are removed on access or capacity eviction.
Malformed entries and storage-write failures are misses rather than successes.
Writes use atomic replacement. No pickle or executable cache serialization.
Repository deletion clears its disposable cache; account deletion also clears
caches for previously deleted repositories. Existing backups retain old copies
under the existing backup retention policy.

Locks target the current single-worker deployment. Multiple API workers/instances
require shared locking before enabling them. Model artifacts changed in place
under the same model name require a pipeline/version change and reindex.

## Validation and release

`scripts/check_backend.py` uses temporary SQLite/Chroma, mocked AI, and no dotenv
files. It tests hits, forced refresh, source/model/rule invalidation, concurrent
requests, failure retry, bounded/corrupt/expired caches, credit preservation and
account/deletion isolation. Frontend tests cover hit feedback and duplicate clicks.

After publishing the tested commit, update the Azure checkout with a fast-forward
pull, build the backend, and recreate only that service when no jobs are running:

```sh
cd /home/azureuser/codelens-ai
git pull --ff-only origin main
sudo docker compose --env-file /etc/codelens/runtime.env -f deploy/azure-vm/compose.yaml -f deploy/azure-vm/compose.https.yaml build backend
sudo docker compose --env-file /etc/codelens/runtime.env -f deploy/azure-vm/compose.yaml -f deploy/azure-vm/compose.https.yaml up -d --no-deps backend
curl --fail http://127.0.0.1:8000/ready
```

Vercel deploys the frontend from main. In a signed-in account, run analysis twice:
the second request should reuse the first job. A fresh scan should create a new
job without using an import credit. Reopen a file summary and confirm reuse;
refresh it explicitly to request a new generation. A different account must still
receive 404 for those resource IDs. Do not delete real accounts for release tests.
