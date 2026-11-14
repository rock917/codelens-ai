# Repository URL validation

CodeLens accepts HTTPS repository root URLs on `github.com` and `gitlab.com`.
GitHub repository names may contain ASCII letters, digits, `.`, `_` and `-`,
including leading punctuation such as `-crop-prediction-model`, `.github`, and
`_project`. The owner segment is validated separately. Repository names are
limited to GitHub's 100-character maximum.

GitLab supports nested namespace paths. Its current server path validator permits
leading dots and underscores, repeated punctuation, and trailing punctuation in
project names. Paths starting with `-`, namespaces ending in `.`, and paths ending
in `.git` or `.atom` are excluded (after removing the clone suffix). This follows
the server implementation rather than imposing the stricter wording in some
GitLab documentation. Remote lookup remains authoritative for existence and
reserved names.

Normalization accepts surrounding spaces, one trailing slash, the optional `.git`
clone suffix, HTTPS port 443, and URL-encoded allowed characters. GitHub paths
are lowercased; GitLab path case is preserved. These equivalent URL forms share
the same cache/admission key, so an unchanged repository does not reserve another
credit. Existing saved keys do not need a migration.

Unsupported hosts/schemes, credentials, other ports, branch/file URLs, nonempty
query strings/fragments, control characters, empty/dot path segments, encoded
slashes/backslashes and disallowed characters are rejected before remote lookup
or credit reservation. URL decoding happens once and does not introduce path
separators. Git is invoked with an argument array, never a shell command string.

References:
- [GitHub repository creation and naming](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [GitLab server path validation](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/path_regex.rb)
- [GitLab naming documentation](https://docs.gitlab.com/user/reserved_names/)

Regression coverage in `scripts/check_backend.py` includes valid punctuation,
normalization, GitLab subgroups, the reported leading-hyphen repository, equivalent
URL deduplication, malformed URLs, rejection without network/credit use, and Git
argument handling.
