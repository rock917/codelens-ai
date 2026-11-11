-- Run in the Supabase SQL editor as the database owner BEFORE serving this release.
-- App data is accessed only by the trusted FastAPI database role, never the browser.
-- Idempotent and transactional. Legacy rows remain unowned and inaccessible through the API.
BEGIN;
ALTER TABLE public.repositories ADD COLUMN IF NOT EXISTS owner_id VARCHAR;
CREATE INDEX IF NOT EXISTS ix_repositories_owner_id ON public.repositories(owner_id);
ALTER TABLE public.repositories ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.repositories FROM anon, authenticated, PUBLIC;
ALTER TABLE public.files ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.files FROM anon, authenticated, PUBLIC;
ALTER TABLE public.symbols ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.symbols FROM anon, authenticated, PUBLIC;
ALTER TABLE public.code_chunks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.code_chunks FROM anon, authenticated, PUBLIC;
ALTER TABLE public.analysis_issues ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.analysis_issues FROM anon, authenticated, PUBLIC;
ALTER TABLE public.repository_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.repository_jobs FROM anon, authenticated, PUBLIC;
ALTER TABLE public.repository_summaries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.repository_summaries FROM anon, authenticated, PUBLIC;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.conversations FROM anon, authenticated, PUBLIC;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.messages FROM anon, authenticated, PUBLIC;
COMMIT;
