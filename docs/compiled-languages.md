# Java, Go and C++ support

Import a public Git repository or ZIP through the existing repository workflow.
The new language adapters use pinned Tree-sitter grammars. They parse source only:
no code, compilers, build scripts, package installation or C++ preprocessors run.
No database migration or authentication configuration change is needed.

| Language | Files | Symbols and dependencies |
| --- | --- | --- |
| Java | `.java` | Named classes, interfaces, enums, records, constructors, methods, overloads and imports |
| Go | `.go` | Functions, receiver methods, structs, interfaces, named types, generics and imports with aliases |
| C++ | `.cpp`, `.cc`, `.cxx`, `.C`, `.h`, `.hpp`, `.hh`, `.hxx`, `.ipp`, `.tpp` | Named classes, structs, enums, namespaces, aliases, function definitions/prototypes, inline methods, constructors/destructors, templates and includes |

`.h` is ambiguous between C and C++; it is parsed using the C++ grammar. `.c` files
are not covered by this release. Language labels are source classifications, not
claims about how a project's build system compiles them.

## Viewing, search and generation

Explorer and search use theme-aware syntax highlighting. Symbols retain original
source line ranges and signatures. Chunking preserves symbol labels and bounds
long chunks; module-level source and short include/import gaps are indexed too.
Chat citations refer to the same source line numbers.

Go methods whose type is declared in another file remain accessible in Explorer.
Overloads have separate IDs, signatures and line ranges. Test generation selects
the exact symbol ID and uses JUnit 5 for Java, the standard `testing` package for
Go, and GoogleTest for C++. Generated tests are suggestions, not executed tests;
users must review project-specific imports, dependencies, fixtures and build flags.

## Health coverage

These are limited syntax-based heuristics:

- Function length, parameter count, estimated branch complexity and nesting.
- TODO/FIXME and related markers in actual comment nodes, not string contents.
- Potential hardcoded credentials in common string-literal declarations.
- Java: selected legacy algorithms in `MessageDigest`/`Cipher.getInstance` calls.
- Go: selected calls to `crypto/md5`, `crypto/sha1` and `crypto/des`, respecting
  explicit import aliases.
- C++: unbounded buffer operations such as `strcpy`, `strcat`, `gets` and `sprintf`.

Findings require review. This is not compiler/type checking, a dependency audit,
data-flow/taint analysis, macro expansion, or proof that code is secure. No finding
does not mean there are no defects. Abstract declarations/prototypes are navigable
but do not receive function-body metrics. Separate nested functions/lambdas are not
folded into their enclosing function's complexity.

Tree-sitter can recover part of an invalid or unsupported source file. Recoverable
symbols and source remain searchable; Explorer shows a partial-parse notice. The
entire file is excluded from health scoring and listed in coverage exclusions,
instead of receiving a misleading perfect score. Unsupported macro-heavy or new
language syntax may need future grammar updates. Name/type resolution across
files, overload resolution and C++ specialization semantics are not performed.

Source size is limited to 1 MiB per file; syntax-tree traversal is bounded to
200,000 named nodes. Grammar failures are not treated as successful scans.

## Refreshing existing repositories

Import the same unchanged repository again to refresh an old index. The pipeline
version includes the adapters and pinned grammar dependencies, so stale parsing
and embeddings are rebuilt through the existing credit-preserving reindex path.
Source/analyzer changes invalidate health results; unchanged rescans reuse them.
Saved chats and account ownership continue to follow the existing storage rules.

## Checks

`scripts/check_backend.py` exercises mixed-language ZIP imports, symbol boundaries,
overloads, Go receivers, C++ headers/templates, malformed syntax, security-pattern
false positives in comments/strings, search, chat, generation, cache reuse, reindex
and cross-account rejection. AI calls are mocked and databases are temporary.
Frontend tests cover new-language file selection, overload IDs and parse notices.
