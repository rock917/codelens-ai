# Azure migration preparation

Scope agreed on 2026-11-11: keep Vercel and Supabase; move FastAPI, CPU embeddings,
uploaded repositories, Chroma and the model cache from Render to Azure.
Azure resources have not been provisioned. Publishing main can trigger existing
Vercel/Render deployments; it does not complete the database migration or Azure cutover.

## Current release and required startup order

The owner has authorized consolidating the prepared code on main and preparing Azure.
Google/GitHub sign-in is the current launch scope. Keep `VITE_ENABLE_EMAIL_AUTH`
absent or `false`; SMTP/email-password, the lifetime quota and caching come later.

Do not defer the ownership migration until after starting this backend: startup
intentionally refuses the old/publicly accessible schema. Back up and validate the
migration before starting against the production database. Stop the older API when
applying the migration so it cannot continue accepting unauthenticated requests.
An Azure VM/container can be prepared privately first, but is not a working public
release until migration, Auth settings and end-to-end checks pass.

Pushing main may redeploy existing Vercel/Render services automatically. A new Render
backend will fail startup if its migration is missing. A Vercel build without the
public Supabase settings displays sign-in unavailable. Configure environment values
through the host dashboards; do not paste secrets into chat or Git. To preserve the
old demo until cutover, pause automatic deployments in the host dashboards before a
release push; do not assume a repository file overrides current dashboard settings.

## Hosting choice to review

Start by pricing **one Linux x64 VM with 2 vCPUs and 4 GiB RAM**, using a managed
disk, in a region close to the existing Supabase database. This is a proposed
starting size, not a measured capacity guarantee. Check student-subscription
quota, SKU availability and the complete monthly estimate before creation.
CPU inference works locally; a GPU VM is not necessary for the initial migration.

The current Chroma implementation stores a SQLite database and vector files on
disk. A VM keeps that storage on a local filesystem backed by a managed disk.
Do not put its SQLite files on an arbitrary SMB/NFS share just to make a container
deployment persistent. SQLite documents network filesystem locking and
corruption risks: https://www.sqlite.org/useovernet.html.
Azure managed disks provide persistent storage:
https://learn.microsoft.com/en-us/azure/virtual-machines/managed-disks-overview.

App Service or Container Apps remains an option after designing and testing a
suitable separate vector-storage service. The current application has in-process
jobs and must use **one API worker, one backend instance**. Multiple instances
require a durable queue and coordinated recovery, not just a scale setting.

## Student credit budget

Azure for Students provides $100 for use within 12 months; it is not $100 each
month: https://learn.microsoft.com/en-us/azure/education-hub/faq.
To spread $100 over a full year, the average total spend must be below $8.33/month.
Do not assume the proposed always-on VM fits that target.

Price compute, managed disk, public IP, egress and backup together in the selected
region. Record the total estimate and expected credit lifetime before approval.
For a demonstration deployment, deallocating the VM when unused can reduce compute
cost, but the API will be unavailable until it is started. Retained disks and other
resources can still incur charges. See:
https://learn.microsoft.com/en-us/azure/virtual-machines/states-billing.
Budget alerts notify; they do not themselves stop resources:
https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets.

## Prepared container configuration

`deploy/azure-vm/compose.yaml` builds the backend, exposes port 8000 only on the VM's
loopback interface, runs one worker and persists uploads, vectors and model cache
in a named Docker volume. Keep Docker's data directory on the managed disk, not
the VM's temporary disk. This Compose configuration has not been run in Docker
because Docker Desktop's Linux engine was unavailable during the local audit.

The backend Docker build uses explicit source copies and an allowlist build
context, excluding dotenv files, local virtual environments and existing data.
Supply `DATABASE_URL` and `GROQ_API_KEY` privately on the host. Set `GROQ_MODEL` to
the model you actually use. Never commit those values or paste them into this chat.

Once a VM and HTTPS endpoint are selected, the operator can run from the repository:

```sh
docker compose -f deploy/azure-vm/compose.yaml up -d --build
curl --fail http://127.0.0.1:8000/health
```

This command requires secure runtime configuration first. Add a reverse proxy
with a trusted HTTPS certificate and WebSocket/SSE support. Expose HTTPS through
the Azure network security group; keep the raw backend port private. A domain or
approved DNS hostname and TLS configuration still need to be chosen. The existing
account implementation requires the migration, Supabase Auth configuration and
acceptance checks in [ACCOUNTS.md](ACCOUNTS.md) before deployment. Configure
`SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` on the backend and the corresponding
VITE variables on Vercel. Quotas and production ingestion limits remain pending.

## Optional HTTPS proxy

`compose.https.yaml` adds Caddy with persistent certificate storage and proxies both
WebSocket progress and streamed chat. Set `API_DOMAIN` to a public DNS hostname
pointing to the VM's static public IP. Use a domain you control or an available Azure
public-IP DNS label. Allow inbound TCP 80/443 and restrict SSH to your own source IP;
do not expose port 8000 publicly. DNS, firewall rules and certificate issuance must
be tested on the actual host. See [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
and [reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

Supply these host settings in a private file outside the repository, for example
`/etc/codelens/runtime.env`, readable only by the deployment operator. This is a
configuration specification, not a request to share values:

| Setting | Required value |
| --- | --- |
| DATABASE_URL | Existing Supabase SQL connection for a trusted backend role |
| GROQ_API_KEY | Existing Groq credential |
| GROQ_MODEL | Model available to your account |
| SUPABASE_URL | `https://vwzaoyvpruwjohmbugtm.supabase.co` |
| SUPABASE_PUBLISHABLE_KEY | Same project's public Auth key |
| FRONTEND_URL | `https://codelens-ai-five.vercel.app` |
| API_DOMAIN | Selected public API hostname, without scheme/path |

From the repository root on the VM, after the migration and settings are ready:

```sh
docker compose --env-file /etc/codelens/runtime.env -f deploy/azure-vm/compose.yaml -f deploy/azure-vm/compose.https.yaml config --quiet
docker compose --env-file /etc/codelens/runtime.env -f deploy/azure-vm/compose.yaml -f deploy/azure-vm/compose.https.yaml up -d --build
curl --fail http://127.0.0.1:8000/health
```

Use `config --quiet`; rendering the full configuration can print credentials.
Verify `https://YOUR_API_HOST/health` separately. The public `/health` endpoint checks
liveness, not authentication or embeddings; it is not release acceptance by itself.
Before public access, `/repositories` without a bearer token must return 401, and
an authenticated user must not see another user's repository IDs.

To validate the Compose wiring locally without secrets or starting containers:

```sh
python scripts/check_azure_config.py
```

This check supplies dummy values and an explicit empty environment file. It checks
configuration only; it does not validate the Docker image, Caddy runtime, real
Supabase/PostgreSQL permissions, DNS/TLS or Azure networking. Never use
`docker compose down -v` during normal updates: it deletes persistent volumes.

## Cutover and persistence checks

1. Verify the chosen region, quota, estimated spend and HTTPS hostname.
2. Back up Supabase and inventory the existing Render uploads/vectors. Stop
   ingestion on Render before starting the replacement against the same database:
   startup recovery marks interrupted ingestion records as failed.
3. Copy uploads and Chroma together during a stopped-write window if available.
   Supabase metadata alone does not contain the vector index or source files.
   If Render data has already disappeared, repositories need re-upload/re-clone;
   the current incremental indexer does not rebuild missing vectors for unchanged
   files. Do not delete existing Supabase records without a reviewed migration.
4. Validate and apply `backend/migrations/001_private_accounts.sql` after backup
   and stopping the old API. Confirm the trusted backend role can access the tables
   and browser roles cannot. Assign only the selected legacy repositories to their
   verified owner. Start the Azure backend with its required settings.
   Download/warm the embedding model once before inviting users.
5. Test Google/GitHub sign-in, logout, token refresh and two-account isolation first.
   Then test ZIP and GitHub ingestion, health during ingestion, vector search, real Groq
   chat, streaming, file viewing and static analysis. Test a representative large
   repository while monitoring memory and disk use.
6. Restart the container and the VM; confirm source files, search results and model
   cache persist. Back up the named volume while writes are stopped and test restore.
7. Set Vercel `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` for the same
   Auth project. Keep `VITE_ENABLE_EMAIL_AUTH=false`. Change Vercel's `VITE_API_URL` to the new HTTPS API origin and redeploy the
   frontend (Vite embeds this at build time). Verify CORS from the actual Vercel
   origin, WebSockets and streaming in a browser.
8. Keep a rollback path to Render until acceptance checks pass. Do not run ingestion
   concurrently on both backends against the shared database.

## Remaining information

Azure login/subscription selection, allowed region and VM quota, remaining credit,
desired credit lifetime/uptime, HTTPS hostname, and a secure way to supply runtime
secrets are needed before deployment. The owner authorized pushing the prepared code
to main. Azure resource creation and cutover remain separate steps after selecting
the configuration, reviewing the cost estimate and completing required migration checks.
