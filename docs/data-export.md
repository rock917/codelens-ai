# Account data export

Settings → Export your data → Download my data (JSON) calls the authenticated
`GET /account/export` endpoint. It costs no analysis credits and does not run AI,
change account data, or require a migration or new database table.

Version 1 contains the account ID/email, usage totals/history (including usage
for deleted repositories), repository/file metadata, symbols, saved summaries,
analysis findings/run coverage, conversations and saved messages/source references.
IDs link records across arrays; the manifest includes row counts. Structured JSON
fields are decoded; older non-JSON text is retained. Timestamps without an offset
reflect existing database timestamps (the service uses UTC).

This is a portable data copy, not a restore archive. Source-file archives,
raw code chunks, embeddings/vector indexes, authentication secrets and server logs
are excluded. Chats, findings, summaries and symbol signatures/docstrings can
still contain source excerpts. The download should be kept private. Only saved
work is included; an in-progress response/import may not yet appear.

Every table is filtered by the verified account ID through repository ownership,
or directly by owner ID for usage. Legacy unowned records are excluded. The
existing account-deletion guard applies. PostgreSQL exports use a repeatable-read,
read-only transaction so the arrays come from the same database snapshot.

No persistent server copy or public download URL is created. A private temporary
spool keeps the first 1 MiB in memory, then uses the container's OS temporary
storage. Each export is limited to 25 MiB, 200,000 rows and 60 seconds of preparation.
Limits return an error before sending an attachment; exports are never silently
truncated. Temporary storage is closed after download, preparation failure,
cancellation, or disconnect. OS temporary files also close when the process exits.

The supported single-worker service permits two simultaneous exports, one per
account, with three attempts per account per ten minutes. These guards are
in-process and reset on restart. Multi-worker deployment would need shared guards.
Responses are attachments with `Cache-Control: private, no-store`. Frontend requests
cancel on unmount/account change and use a short-lived Blob URL; the browser saves
the user's downloaded file normally. No browser storage is used for export content.

For exports exceeding these limits, contact the support address linked in Privacy.
Do not delete data to reduce the export size. No automatic email delivery or
background export queue is implemented.

Validation: isolated backend tests cover ownership/legacy isolation, saved chats,
pagination, usage after repository deletion, excluded fields, rate/concurrency
limits, preparation failures and interrupted-download cleanup. Frontend tests
cover real-response downloads, duplicate clicks, errors and account changes.
