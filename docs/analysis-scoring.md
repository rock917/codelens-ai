# Analysis scoring and scan states

Static analysis supports Python, JavaScript and TypeScript. Repository ingestion indexes code; a separate scan produces findings. An unrun scan has no health score. Existing findings without coverage metadata are retained as legacy results; run analysis again to compute the new score.

The density-v1 score is a heuristic for prioritizing review, not a security certification. Findings are weighted critical=15, high=8, medium=3, low=1. Weighted density is the sum of weights multiplied by 1,000 and divided by max(1,000, scanned lines). Score = round(100 / (1 + density / 20)). Critical findings cap the score at 49 and high findings at 79. Display findings and scan coverage alongside the score; rule-based findings may be false positives.

Scans use existing repository_jobs rows (job_type ANALYSIS), so no schema migration is needed. The PostgreSQL repository row lock serializes scan creation for a repository. Background scans own their database sessions and run file/AST work off the event loop. Results are replaced in a single transaction. Failures retain the previous successful results; missing source files cause failure, not a clean score. A completed scan with no supported files has no score. Startup recovery marks interrupted scans failed on the supported single-worker deployment.

Email signup/sign-in/reset already exist. After configuring Supabase SMTP, set VITE_ENABLE_EMAIL_AUTH=true in Vercel Production and deploy again. Keep email confirmation enabled and retain both callback redirect URLs. Test a real confirmation and password-reset flow in the same browser used to request each link.
