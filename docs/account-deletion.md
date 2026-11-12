# Account deletion

Settings → Delete account removes the authenticated user's CodeLens data and
Supabase Auth identity. There is no user-ID input: the server derives ownership
from the token validated by Supabase. Confirmation requires the matching email,
the exact word DELETE, and a password/OAuth sign-in in the last ten minutes.
JWT refresh is not reauthentication; only the verified token's AMR timestamp counts.

The single-worker API keeps request leases through streaming and background work.
Deletion refuses active requests/imports/jobs, blocks further work, and records a
private durable request. Cleanup removes source directories and Chroma collections
for current repositories and IDs retained in the user's admission ledger, then
removes SQL children, repositories and usage, then calls Supabase's admin hard-delete
endpoint. Missing storage/Auth records are safe to retry; other failures retain
the request. A loop retries every minute and after restarts. The request itself is
removed after successful completion. Detached summarization participates in leases.
A two-minute in-memory cache blocks late Auth responses for a just-deleted UUID;
it is not a retained signup/usage identifier and disappears on process restart.

No identity hash is retained to prevent new signups. A newly registered account
gets a new allowance. Google/GitHub accounts and upstream repositories are untouched.
Automatic backups retain seven successful copies; old/manual copies need separate
operator removal. Never restore old application rows without reconciling deleted
Supabase identities and purging data that should remain deleted.

## Deployment

1. Create and restore-test a backup. Apply `003_account_deletion.sql` as the SQL
   owner before starting this release. It enables RLS and revokes browser access.
2. Deploy the code. Without the admin key, Settings explains that self-service
   deletion is unavailable; existing login and workspace functions continue.
3. On the VM, run `sudo python3 scripts/configure_account_deletion.py`. Paste the
   **server secret / legacy service_role key** into the hidden prompt, never into
   chat, Git, Vercel, a command argument or any `VITE_` variable. The helper checks
   admin access to the existing project without reading or deleting a real user.
   It writes `/etc/codelens/account-admin.env`, root-only, without overwriting
   existing settings. The Compose optional env file passes it only to the backend.
4. Recreate the backend:

```sh
sudo docker compose --env-file /etc/codelens/runtime.env -f deploy/azure-vm/compose.yaml -f deploy/azure-vm/compose.https.yaml up -d --no-deps --force-recreate backend
curl --fail http://127.0.0.1:8000/ready
```

5. Test with a disposable account only: create a small repository and chat, delete
   the account, verify its Auth record/data/storage are gone and another account
   still works. Never use a real owner's account for a destructive acceptance test.

For a pending deletion, inspect only phase/count/age in `account_deletions`.
Do not manually remove the request before cleanup: it blocks further writes and
contains the storage inventory needed for retries. Missing or rotated admin
credentials leave cleanup pending until configured correctly.

## Checks

`scripts/check_backend.py` covers ownership, old deleted repositories, SQL/storage
cleanup, partial failures, retries, fresh sign-in checks and active stream protection.
Frontend tests cover confirmation, cancellation, unconfigured state and errors.
`scripts/check_usage_postgres.py` applies all migrations twice against an isolated
PostgreSQL database and checks grants. Auth deletion is mocked in automated tests;
the live provider requires the separate disposable-account test after key setup.
