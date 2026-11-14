"""One scoring policy shared by analysis, repository counts and the UI."""
SCORE_VERSION = 'risk-density-v2'
RETIRED_RULES = frozenset({'LONG_LINE', 'WEAK_JWT_ALG'})
SECURITY_RULES = frozenset({
    'HARDCODED_PASSWORD', 'HARDCODED_SECRET', 'HARDCODED_TOKEN', 'HARDCODED_AWS_KEY',
    'HARDCODED_CREDENTIAL', 'WEAK_HASH_MD5', 'WEAK_HASH_SHA1', 'WEAK_CIPHER_DES',
    'WEAK_CRYPTO', 'SQL_INJECTION', 'UNSAFE_EVAL', 'UNSAFE_DESERIALIZATION',
    'COMMAND_INJECTION', 'UNBOUNDED_BUFFER_OPERATION',
})
HEALTH_RULES = SECURITY_RULES | {'HIGH_COMPLEXITY', 'DEEP_NESTING'}


def score_impact(issue_type):
    if issue_type in RETIRED_RULES:
        return False, 'This rule has been retired and does not affect health.'
    if issue_type in ('HIGH_COMPLEXITY', 'DEEP_NESTING'):
        return True, 'Excessive branching or nesting makes behavior harder to reason about and test.'
    if issue_type.startswith('HARDCODED_') and issue_type in HEALTH_RULES:
        return True, 'A credential-like literal may expose access to a service. Review whether it is a real secret.'
    reasons = {
        'SQL_INJECTION': 'A dynamically constructed SQL statement reaches a database execution call; parameter binding avoids mixing data with SQL.',
        'COMMAND_INJECTION': 'A dynamically constructed command reaches a shell. Untrusted values may be interpreted as commands.',
        'UNSAFE_EVAL': 'Dynamic Python evaluation can execute code; review the source and trust level of its input.',
        'UNSAFE_DESERIALIZATION': 'Loading pickle data can execute code; review whether input can be controlled by another party.',
        'UNBOUNDED_BUFFER_OPERATION': 'This operation does not enforce buffer capacity and may write beyond the destination.',
    }
    if issue_type in reasons:
        return True, reasons[issue_type]
    if issue_type in SECURITY_RULES:
        return True, 'A legacy cryptographic primitive is used. Review its purpose; a checksum is not automatically a security vulnerability.'
    return False, 'A maintainability or style suggestion, not evidence of a defect. It does not reduce the health score.'
