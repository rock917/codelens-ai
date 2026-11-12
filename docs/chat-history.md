# Private conversation history

Conversations and messages remain in the existing Supabase PostgreSQL tables. Access is inherited from the owning repository and checked on every list, history, send, rename and delete API request. No new database migration is required.

The API commits the question before starting generation. A completed answer, its source references and the completion marker are committed together before sending the stream's `done` event. Failed, empty or interrupted replies do not appear as completed answers in saved history. Their questions remain available. Reopening the conversation shows saved messages; a user may send the unanswered question again.

Existing repository_jobs rows track active replies with `CHAT:<conversation_id>` job types. A PostgreSQL row lock serializes new replies in each conversation. A duplicate send, or an attempt to delete a conversation while it is generating, returns 409. Stream cancellation clears the active job; startup recovery marks interrupted jobs failed on the supported single-worker deployment.

The UI opens the most recently updated conversation when a repository is selected. History is stored on the server, not in browser storage. Navigation cancels the current stream and ignores stale callbacks. Opening an active conversation polls until its reply completes. Rename accepts 1–120 characters. Delete requires a UI confirmation and removes only that conversation, its messages and associated reply jobs. Deleting the entire repository still removes its conversations through the existing cascade. Reindexing an existing repository does not delete chats; importing a separate repository creates a separate workspace.

Validation covers database reconnection, source preservation, message order, failed/interrupted responses, duplicate sends, rename/delete isolation, fragmented stream events, navigation races, and history reopening. Automated tests use disposable data and mocked AI/authentication services.
