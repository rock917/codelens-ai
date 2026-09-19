import ast
import re
from typing import List
from dataclasses import dataclass

@dataclass
class SecurityIssue:
    file_path: str
    line: int
    issue_type: str
    severity: str
    message: str
    suggestion: str
    code_snippet: str = ""

# Patterns for detecting secrets
SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{3,}["\']', "HARDCODED_PASSWORD"),
    (r'(?i)(secret|secret_key|api_key|apikey)\s*=\s*["\'][^"\']{3,}["\']', "HARDCODED_SECRET"),
    (r'(?i)(token)\s*=\s*["\'][^"\']{8,}["\']', "HARDCODED_TOKEN"),
    (r'(?i)(aws_access_key|aws_secret)\s*=\s*["\'][^"\']{8,}["\']', "HARDCODED_AWS_KEY"),
]

# Weak crypto patterns
WEAK_CRYPTO_PATTERNS = [
    (r'\bmd5\b', "WEAK_HASH_MD5", "MD5 is cryptographically broken"),
    (r'\bsha1\b', "WEAK_HASH_SHA1", "SHA1 is weak for security use"),
    (r'\bDES\b', "WEAK_CIPHER_DES", "DES is insecure"),
    (r'algorithm\s*=\s*["\']HS256["\']', "WEAK_JWT_ALG", "HS256 with weak secret is vulnerable"),
]

def analyze_security(
    file_path: str,
    content: str,
    language: str
) -> List[SecurityIssue]:
    issues = []
    lines = content.splitlines()

    # 1. Pattern-based detection (all languages)
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()

        # Skip comments
        if line_stripped.startswith('#') or line_stripped.startswith('//'):
            continue

        # Check secret patterns
        for pattern, issue_type in SECRET_PATTERNS:
            if re.search(pattern, line):
                issues.append(SecurityIssue(
                    file_path=file_path,
                    line=i,
                    issue_type=issue_type,
                    severity="CRITICAL",
                    message=f"Hardcoded credential detected",
                    suggestion="Use environment variables or a secrets manager",
                    code_snippet=line.strip()[:100]
                ))

        # Check weak crypto
        for pattern, issue_type, desc in WEAK_CRYPTO_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(SecurityIssue(
                    file_path=file_path,
                    line=i,
                    issue_type=issue_type,
                    severity="HIGH",
                    message=desc,
                    suggestion="Use SHA-256 or stronger algorithms",
                    code_snippet=line.strip()[:100]
                ))

    # 2. Python-specific AST analysis
    if language == "python":
        issues.extend(_analyze_python_security(file_path, content, lines))

    return issues


def _analyze_python_security(
    file_path: str,
    content: str,
    lines: List[str]
) -> List[SecurityIssue]:
    issues = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        # SQL injection detection
        if isinstance(node, (ast.Call, ast.Expr)):
            node_str = ast.dump(node)
            if 'f"SELECT' in node_str or "f'SELECT" in node_str:
                line = getattr(node, 'lineno', 0)
                issues.append(SecurityIssue(
                    file_path=file_path,
                    line=line,
                    issue_type="SQL_INJECTION",
                    severity="CRITICAL",
                    message="Possible SQL injection via f-string query",
                    suggestion="Use parameterized queries instead",
                    code_snippet=lines[line-1].strip()[:100] if line > 0 else ""
                ))

        # Unsafe exec/eval
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ('eval', 'exec'):
                    line = node.lineno
                    issues.append(SecurityIssue(
                        file_path=file_path,
                        line=line,
                        issue_type="UNSAFE_EVAL",
                        severity="CRITICAL",
                        message=f"Use of {node.func.id}() is dangerous",
                        suggestion="Avoid eval/exec with untrusted input",
                        code_snippet=lines[line-1].strip()[:100]
                    ))

            # Unsafe deserialization
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == 'loads':
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == 'pickle':
                            line = node.lineno
                            issues.append(SecurityIssue(
                                file_path=file_path,
                                line=line,
                                issue_type="UNSAFE_DESERIALIZATION",
                                severity="HIGH",
                                message="pickle.loads() can execute arbitrary code",
                                suggestion="Use JSON or safer serialization formats",
                                code_snippet=lines[line-1].strip()[:100]
                            ))

        # OS command injection
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ('system', 'popen', 'run', 'call'):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id in ('os', 'subprocess'):
                            if node.args:
                                # Check if argument is not a literal
                                if not isinstance(node.args[0], ast.Constant):
                                    line = node.lineno
                                    issues.append(SecurityIssue(
                                        file_path=file_path,
                                        line=line,
                                        issue_type="COMMAND_INJECTION",
                                        severity="CRITICAL",
                                        message="Possible command injection vulnerability",
                                        suggestion="Validate and sanitize all command inputs",
                                        code_snippet=lines[line-1].strip()[:100]
                                    ))

    return issues