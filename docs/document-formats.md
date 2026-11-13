# JSON and Jupyter notebooks

Import a Git repository or ZIP as usual. JSON (`.json`) and Jupyter notebooks
(`.ipynb`, nbformat 4) participate in indexing, semantic search, AI chat and file
summaries. Existing account ownership checks and import allowances apply.

## JSON

Explorer validates and formats JSON. Top-level values become search chunks with
JSON Pointer labels (for example `/service` or `/0`). Nested content stays within
its top-level section, with large sections split into smaller chunks. Pointer
escapes use `~1` for `/` and `~0` for `~`.

JSON is data, so validation does not produce a code-health score. Invalid JSON
is listed in Explorer with an error, but is not indexed or summarized. Duplicate
object keys and non-finite numeric values are rejected.

Limits: 1 MiB input, 4 MiB formatted text, 20,000 nodes, nesting depth 64, and
512 characters per object key. Files exceeding the import size limit are skipped.

## Notebooks

Explorer displays code, Markdown and raw cells with their original cell numbers.
Search and chat citations carry cell labels. Line numbers refer to a canonical,
source-only view, not the notebook's underlying JSON. Markdown images, HTML and
external links are not loaded by the notebook viewer.

Saved outputs, execution counts, attachments and other metadata are omitted from
the displayed and indexed content. Original uploaded files still exist in repository
storage and can be included in backups. No notebook code is executed.

Health scans inspect syntactically valid Python code cells when notebook metadata
identifies a Python kernel. Markdown, raw cells and empty code cells are unscored.
Cells with magic commands, shell commands or invalid Python are indexed as source
but excluded from health analysis, with coverage notices. Other or unknown kernels
remain searchable but do not receive a Python health score. Notebook analysis is
per cell; it does not simulate execution order or cross-cell runtime state.

Limits: 10 MiB notebook file, 1 MiB combined cell source, and 1,000 cells. Supported
cell structure and kernel metadata are validated; this is not a full nbformat
schema validator. Unsupported or malformed documents show a validation error.

## Existing repositories and caching

Import an existing repository again to update its index for the new formats.
The parser version change invalidates obsolete indexes and cached processing;
reusing the same repository follows the existing no-extra-credit path. Health
results are invalidated when sources or analyzer versions change.

Only valid indexed document content is sent to file summaries and chat context.
The existing per-repository cache, account isolation, deletion and retention rules
remain in effect. No database migration is required.
