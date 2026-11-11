# Private accounts — phase 1

This release adds email/password registration, email confirmation, password reset,
Google/GitHub sign-in, and an account-owned workspace. It is a first step toward
multi-user production use, not a completed production launch. Nothing here creates
an Azure resource, changes live Supabase settings, or migrates vector storage.

## Current launch scope (11 November 2026)

Launch with Google and GitHub only. The owner has configured both providers and the
production Site URL/redirect URLs, and reports Google OAuth is in production.
Do not recreate providers, rotate credentials or change Google's publishing status.
Actual provider flows are still unverified. Email/password signup and reset are
postponed until custom SMTP is configured and tested.

`VITE_ENABLE_EMAIL_AUTH` defaults to false: email signup/login/reset controls are
hidden, and `/reset-password` redirects to sign-in. Keep it absent or `false` in
Vercel for this release. Setting it to `true` and rebuilding enables the existing
email forms later. This is a frontend feature switch, not a Supabase access rule:
the Email provider remains enabled as requested, so its Auth API remains available.
Backend token and ownership validation is unchanged.

For the OAuth-only launch, email delivery is not a prerequisite for ordinary
Google/GitHub sign-in; do not bypass confirmation checks or enable unverified-email
options to work around account problems. Complete SMTP/password configuration below
before opting into email authentication. The saved reset redirect can remain.

Remaining launch steps: verify Vercel/Render environment settings, validate the
migration on a database copy, back up production and schedule the migration, then
validate the protected backend/frontend and real provider flows before releasing.
This update does not authorize a production deployment.

## Architecture

- Vercel serves React. Supabase Auth handles passwords, confirmation emails and
  OAuth. The browser uses the public publishable key (legacy anon key also works).
- FastAPI validates each bearer token with the project's `/auth/v1/user` endpoint.
  It accepts a confirmed, non-anonymous account and takes its owner ID from that
  response, never from an upload body. Auth outages fail closed with HTTP 503.
- PostgreSQL stores `repositories.owner_id`. File, symbol, analysis, generation,
  search and chat access is checked through the owning repository. Lists filter
  by owner; unauthorized resource IDs return 404. Private responses use no-store.
- Chroma and uploads remain on the backend's persistent disk. Existing per-repository
  collection IDs remain unchanged. There is no shared cache between accounts.
- Progress sockets accept the token in their first message, not a URL. They check
  the allowed Origin and repository owner, and revalidate every 30 seconds.
  HTTP polling continues if the socket disconnects or its token expires.
- Supabase app tables are not exposed to browser roles. RLS and revoked grants
  prevent bypassing the FastAPI checks through Supabase's data API. The backend
  SQL connection must use a trusted role with the required table access and RLS
  bypass/table ownership. Never give that connection string to the browser.
- Sessions are managed by the Supabase SDK with PKCE and automatic token refresh.
  Sign-out clears this browser's session and dashboard. Do not assume a previously
  issued access token is instantly invalidated; Supabase token expiration applies.
  See [Supabase sessions](https://supabase.com/docs/guides/auth/sessions).

## Configure before merging/deploying

1. Back up the existing database. Stop the previous unauthenticated API before
   exposing the new client: old API code does not enforce account ownership.
2. For the existing Supabase database, review and run
   `backend/migrations/001_private_accounts.sql` in its SQL editor as database owner.
   It is transactional and repeatable, adds a nullable owner column, enables RLS
   and revokes access by anon/authenticated/PUBLIC on the nine application tables.
   It does not change `auth.users`, delete repositories, or assign ownership.
   A fresh database needs the application tables created before this migration.
   Startup refuses an older schema or publicly accessible PostgreSQL application tables.
3. For the later email/password release, in Supabase Auth enable Email, keep email confirmation enabled, and set a minimum
   password length of 12. The client applies this length for signup/reset; Auth must
   enforce it server-side too. Disable anonymous signup.
4. For the later email/password release, configure custom SMTP for confirmation/reset emails to friends. Supabase's
   built-in sender is restricted to project-team addresses and is not intended for
   production. See [custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp).
   Store SMTP credentials only in Supabase's settings.
5. Enable [Google](https://supabase.com/docs/guides/auth/social-sign-in/auth-google)
   and [GitHub](https://supabase.com/docs/guides/auth/social-sign-in/auth-github)
   providers. Register the callback URL shown by Supabase with each provider
   (normally `https://<project-ref>.supabase.co/auth/v1/callback`). Store provider
   secrets in Supabase only. GitHub sign-in is identity only; this release does not
   request private repository access or use provider tokens to clone repositories.
6. In Auth URL Configuration set Site URL to your frontend origin. Allow these
   exact redirect destinations for each trusted frontend origin:
   `/auth/callback` and `/auth/callback?next=reset`. For local Vite development use
   `http://localhost:5173`; Docker frontend uses `http://localhost:3000`.
   Add your Vercel production domain. Avoid broad production preview wildcards.
   Keep default email templates using Supabase's confirmation URL, or ensure custom
   templates preserve the redirect. PKCE email links must be opened in the same
   browser/device that initiated the flow.
7. Supply these values privately through host environment settings:

   | Backend | Frontend (Vercel build variables) |
   | --- | --- |
   | `SUPABASE_URL` | `VITE_SUPABASE_URL` |
   | `SUPABASE_PUBLISHABLE_KEY` | `VITE_SUPABASE_PUBLISHABLE_KEY` |
   | `FRONTEND_URL` = exact browser origin | `VITE_API_URL` = HTTPS API origin |

   The project URL and publishable key must refer to the same project on both sides.
   The frontend variables are public and embedded at build time; never substitute a
   service-role/secret key. Existing DATABASE_URL and GROQ_API_KEY remain backend-only.
   Docker Compose forwards the public Auth values as frontend build arguments.
8. Deploy the protected backend and rebuild the frontend. Use HTTPS. Configure Auth
   rate limits before enabling general signup. Do not invite users until acceptance
   checks below pass and the remaining usage/ingestion controls are implemented.

## Existing repositories

Legacy rows have NULL ownership and remain invisible to all users. After you sign
up, inspect your UUID in Supabase Authentication → Users. Review the repository IDs
and deliberately assign only your own rows in the SQL editor:

```sql
-- Replace both example strings; do not run unchanged.
UPDATE public.repositories
SET owner_id = 'YOUR_VERIFIED_AUTH_USER_UUID'
WHERE id IN ('A_REPOSITORY_ID_YOU_OWN') AND owner_id IS NULL;
```

Do not automatically claim all unowned rows for the first visitor. Existing files,
conversations and Chroma collections follow their repository's ownership.

For an existing **local SQLite** database, stop the app, back it up, and use a SQLite
client to check `PRAGMA table_info(repositories)`. If `owner_id` is absent, run
`ALTER TABLE repositories ADD COLUMN owner_id VARCHAR;`, then
`CREATE INDEX IF NOT EXISTS ix_repositories_owner_id ON repositories(owner_id);`.
SQLite has no Supabase browser roles; the PostgreSQL RLS migration does not apply.

## Validation and acceptance

Automated checks use temporary SQLite/Chroma, dummy Auth responses and mocked Groq;
they never read project dotenv files or modify production data.

```sh
python scripts/check_backend.py
cd frontend
npm ci
npm test
npm run build
```

Backend checks exercise token rejection, missing configuration, unconfirmed users,
all data routes requiring authentication, two-account isolation, legacy data,
file/conversation mismatches, sockets, path containment and ingestion regressions.
Frontend checks cover email/signup/OAuth/reset forms, errors, session changes,
protected navigation and auth headers on normal requests and SSE.

Before the OAuth-only release, test real Google and GitHub callbacks,
expired/refreshing sessions, logout and two separate browser accounts. Test email
confirmation/reset before later enabling `VITE_ENABLE_EMAIL_AUTH=true`. Verify that
user B cannot access user A's IDs through HTTP or WebSocket. Attempt direct Supabase
REST access to each application table with both anon and signed-in credentials;
it must be denied. The SQL migration and real provider flows have not been executed
against your project. Check live ingestion/search/chat with real Groq after setup.

## Next phases (not implemented in this release)

1. **Lifetime quota and repeat-submission cache:** ten successful new repository
   analyses total per account, no monthly reset. Proposed accounting: reserve a slot
   atomically when accepting a job; consume on success; release on terminal failure.
   Deletion does not refund consumed slots. Count every ingestion entry point and
   prevent concurrent requests from exceeding ten. Display used/remaining slots.
2. Reuse an owner's completed, intact results for the same canonical repository URL,
   resolved commit SHA and pipeline/model version. Hash ZIP contents for uploads.
   Unchanged hits cost no slot, including after the account reaches ten. Changed
   commits require a new analysis. Deduplicate simultaneous submissions and verify
   persisted vectors/files before returning a cache hit. Do not share private data
   across accounts. Reopening an existing dashboard entry never starts a new job.
3. Add durable job execution/retry, clone/archive resource limits, per-user request
   and LLM budgets, deletion cleanup, backups/restore checks and monitoring. Review
   ingestion and file handling before opening general registration. Current in-process
   jobs require one API worker and one instance. Unbounded archive expansion, large
   clones and frequent generation calls can still exhaust resources.
4. Run the Azure deployment and persistence acceptance checks. Keep Supabase SQL/Auth,
   Vercel frontend, and Chroma on Azure's persistent managed disk as agreed.
