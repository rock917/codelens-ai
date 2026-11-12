# Lifetime analysis allowance

Each account gets ten successful repository imports for its lifetime. Ingestion reserves a slot before work starts. READY commits usage; FAILED releases the reservation. Health scans, chat and reopening saved repositories do not consume another credit. Deletion does not erase the usage ledger. Accounts already above ten retain access to their results but cannot start new imports.

An account-scoped database lock serializes admissions. Cache lookup happens before the allowance check, so identical submissions work even at the limit and simultaneous duplicates share the same import. Another account never receives a cached repository belonging to someone else.

GitHub/GitLab root URLs are normalized and the default-branch HEAD is resolved before admission. That exact commit is fetched for ingestion. A changed commit requires confirmation, creates a separate repository snapshot, and retains the old results and chats. A failed or unavailable fetch uses no credit. ZIP reuse matches the SHA-256 of the entire archive: repackaging the same source into different ZIP bytes is a new import.

Apply `backend/migrations/002_analysis_usage.sql` as database owner before starting this release. Back up first and pause ingestion during migration. Both new tables have RLS and no browser-role privileges. The migration is transactional and idempotent; it seeds existing owned repositories once. Existing successful imports count toward the limit. Existing Git clones can have their revision cache populated from their local checkout using `scripts/backfill_revision_cache.py`; never infer an old snapshot from today's remote HEAD. Older ZIPs without their original archive cannot be matched retroactively.

On the supported single-worker deployment, startup recovery releases interrupted reservations and marks their repositories failed. Reservations and finished usage survive deletion and restart. The UI displays completed, reserved and available counts separately. Unit/integration checks cover contention, cache isolation, failures, deletion, restart and changed-commit confirmation.
