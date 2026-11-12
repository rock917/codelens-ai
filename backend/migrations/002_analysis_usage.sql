-- Run as the database owner after a backup, before serving this release.
-- Existing owned READY repositories count once; deleted usage remains durable.
BEGIN;
CREATE TABLE IF NOT EXISTS public.account_usage (owner_id VARCHAR PRIMARY KEY);
CREATE TABLE IF NOT EXISTS public.analysis_admissions (
    repository_id VARCHAR PRIMARY KEY,
    owner_id VARCHAR NOT NULL,
    source_key VARCHAR NOT NULL,
    revision VARCHAR NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('RESERVED', 'COMPLETED', 'FAILED')),
    created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_analysis_admissions_owner_id ON public.analysis_admissions(owner_id);
CREATE INDEX IF NOT EXISTS ix_admission_cache ON public.analysis_admissions(owner_id, source_key, revision);
ALTER TABLE public.account_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_admissions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.account_usage, public.analysis_admissions FROM anon, authenticated, PUBLIC;
INSERT INTO public.account_usage(owner_id)
SELECT DISTINCT owner_id FROM public.repositories WHERE owner_id IS NOT NULL
ON CONFLICT DO NOTHING;
INSERT INTO public.analysis_admissions(repository_id, owner_id, source_key, revision, status, created_at)
SELECT id, owner_id,
    CASE WHEN source_type = 'github' AND source_url IS NOT NULL THEN
        CASE WHEN source_url ILIKE 'https://github.com/%' THEN lower(regexp_replace(rtrim(source_url, '/'), '\.git$', ''))
             ELSE regexp_replace(rtrim(source_url, '/'), '\.git$', '') END
        ELSE 'legacy:' || id END,
    'legacy:' || id,
    CASE WHEN status = 'READY' THEN 'COMPLETED' WHEN status = 'FAILED' THEN 'FAILED' ELSE 'RESERVED' END,
    created_at
FROM public.repositories WHERE owner_id IS NOT NULL
ON CONFLICT DO NOTHING;
COMMIT;
