# VM backups and resource protection

This setup supports one API worker on the existing Azure VM. It does not create
paid Azure services. Supabase remains the database and identity provider.

## Limits

Authenticated accounts receive 240 API requests/minute, with lower limits of 10
AI requests/minute and 200/day, 5 imports or scans/minute, and 30 searches/minute.
The global pre-auth limit is 600 requests/minute with 24 active HTTP requests.
HTTP 429 responses include Retry-After. These in-memory limits reset on process
restart and are not a durable billing allowance. The separate lifetime allowance
of 10 successful imports stays in PostgreSQL and survives restarts and deletion.

At most four imports can be reserved globally, two per account. Duplicate cached
imports remain reusable while the queue is full. Model calls run two at a time,
with a five-second slot wait and a 90-second execution deadline.

ZIP files are streamed to disk, limited to 100 MiB compressed, 250 MiB extracted,
and 2,000 entries. Unsafe paths, symlinks, encrypted entries and duplicate paths
are rejected. Git working trees are checked against 2,000 files / 250 MiB after
fetch and checkout; this is not a hard limit on Git transfer size. Fresh imports
require 2 GiB free disk space. Caddy caps HTTP request bodies at 101 MiB.

## Automatic backups

Install from the repository root on the VM:

```sh
sudo install -d -m 700 /opt/codelens
sudo install -m 700 deploy/azure-vm/ops.py /opt/codelens/ops.py
sudo install -m 644 deploy/azure-vm/codelens-backup.service deploy/azure-vm/codelens-backup.timer deploy/azure-vm/codelens-monitor.service deploy/azure-vm/codelens-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now codelens-backup.timer codelens-monitor.timer
sudo systemctl start codelens-backup.service
```

An hourly timer attempts one backup every 24 hours, deferring while imports or jobs
are running. The API briefly stops while the public PostgreSQL schema (including
chats and usage) and persistent uploads/Chroma directories are copied together.
The API is restarted even if copying fails; recovery also terminates only this
tool's backup helper containers. Seven completed backups are retained, under
`/home/azureuser/codelens-backups/automatic`, with root-only access. Earlier manual
backups are untouched. Failed partial copies are removed on the next attempt.

Backups exclude Supabase Auth, runtime credentials, and the reproducible embedding
model cache. A manifest stores artifact checksums and the backend image ID. Each
run checks the dump table of contents and reads the compressed storage archive;
this does not replace periodic full restore rehearsals.

**Backups on the VM do not protect against losing its disk.** Off-VM storage is
deferred by the owner. Keep downloaded copies separately until that is configured.
Backups consume VM disk space and are not an Azure managed backup service.

## Health checks

`/health` checks process liveness. `/ready` checks SQL connectivity and the minimum
free disk allowance, returning a generic 503 if either fails. Every five minutes,
the monitor checks readiness, disk space, backup freshness and potentially stalled
jobs. Results are local: no email, SMS or external uptime alert is configured.

```sh
sudo systemctl list-timers 'codelens-*'
sudo cat /var/lib/codelens-ops/health.json
sudo cat /var/lib/codelens-ops/backup.json
sudo journalctl -u codelens-backup.service -u codelens-monitor.service --since today --no-pager
```

The status files contain no credentials or user records. Do not print Docker
environment settings or Compose's expanded configuration when troubleshooting.

## Restore procedure

First verify the selected manifest checksums, then rehearse against an isolated
PostgreSQL 17 database and a new Docker volume, using the recorded backend version.
The included `sudo python3 scripts/check_vm_backup.py` performs an offline restore
rehearsal in disposable containers (512 MiB limits, suitable for the current small
dataset). Increase rehearsal capacity when the dataset grows. It does not modify
Supabase or the production storage volume.

Use `pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error` only
against the isolated disposable database;
create dummy `anon` and `authenticated` roles and apply the migrations to check RLS.
Extract the storage archive only into the isolated volume and check Chroma opens.

For a real recovery, stop application writers and timers, preserve a copy of the
current database and volume, and restore SQL and storage from the same backup.
Production SQL privileges must be restored or reapplied through the migrations.
Keep the existing Supabase Auth project so owner IDs still correspond to accounts.
Do not blindly restore an old snapshot over a live database. Start the API, check
readiness, ownership isolation, saved chats and vector search, then restart timers.
