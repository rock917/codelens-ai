BEGIN;
CREATE TABLE IF NOT EXISTS public.account_deletions (
    owner_id VARCHAR PRIMARY KEY,
    repository_ids TEXT NOT NULL,
    phase VARCHAR NOT NULL DEFAULT 'DATA' CHECK (phase IN ('DATA', 'AUTH')),
    created_at TIMESTAMP DEFAULT now()
);
ALTER TABLE public.account_deletions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.account_deletions FROM anon, authenticated, PUBLIC;
COMMIT;
