"""Conservative source checks: findings require review, not proof of exploitability."""
import ast
import re
from dataclasses import dataclass


@dataclass
class SecurityIssue:
    file_path: str
    line: int
    issue_type: str
    severity: str
    message: str
    suggestion: str
    code_snippet: str = ''


SECRET_NAME = re.compile(r'(?:\w+_)?(?:password|passwd|pwd|secret|secret_key|api_key|apikey|token|access_token|aws_access_key|aws_secret)', re.I)
PLACEHOLDERS = {'changeme', 'change_me', 'your_api_key', 'your_secret', 'your_password', 'your_token', 'placeholder', 'example', 'dummy', 'test', 'test-only-no-network'}


def credential_type(name, value):
    if not SECRET_NAME.fullmatch(name) or not isinstance(value, str) or len(value.strip()) < 4:
        return None
    if value.strip().lower() in PLACEHOLDERS or value.strip().startswith(('${', '{{', '<')):
        return None
    if 'password' in name.lower() or name.lower() in ('passwd', 'pwd'):
        return 'HARDCODED_PASSWORD'
    return 'HARDCODED_SECRET'


def analyze_security(file_path, content, language):
    issues = []
    seen = set()
    def add(line, kind, severity, message, suggestion):
        if (line, kind) not in seen:
            seen.add((line, kind))
            issues.append(SecurityIssue(file_path, line, kind, severity, message, suggestion))

    if language != 'python':
        # Limited JS/TS literal/call checks. No claim of full syntax or data-flow coverage.
        in_comment = False
        for number, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if in_comment:
                in_comment = '*/' not in stripped
                continue
            if stripped.startswith('/*'):
                in_comment = '*/' not in stripped
                continue
            if stripped.startswith(('#', '//')):
                continue
            match = re.match(r'''\s*(?:(?:export\s+)?(?:const|let|var)\s+)?([\w]+)\s*(?::\s*string\s*)?=\s*(["'])(.*?)\2\s*[;,]?\s*(?://.*)?$''', line)
            if match:
                kind = credential_type(match[1], match[3])
                if kind:
                    add(number, kind, 'HIGH', 'Possible hardcoded credential in a string literal', 'Review the value; load real credentials from a secrets manager')
            match = re.search(r'''\b(?:crypto\.)?createHash\(\s*['"](md5|sha1)['"]\s*\)''', line, re.I)
            if match:
                add(number, 'WEAK_HASH_' + match[1].upper(), 'MEDIUM', 'Legacy hash requested; review whether it protects security-sensitive data', 'Use a modern hash when collision resistance is required')
        return issues

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return issues
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = node.module + '.' + alias.name

    def name(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return name(node.value) + '.' + node.attr
        return ''

    def dynamic_sql(node):
        # Only inspect SQL expressions reaching execute(), never arbitrary strings.
        if isinstance(node, ast.JoinedStr):
            literals = [v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            dynamic = any(isinstance(v, ast.FormattedValue) for v in node.values)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            literals = [v.value for v in ast.walk(node) if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            dynamic = True
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'format' and isinstance(node.func.value, ast.Constant):
            literals = [node.func.value.value] if isinstance(node.func.value.value, str) else []
            dynamic = bool(node.args or node.keywords)
        else:
            return False
        return dynamic and any(re.match(r'\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|WITH)\b', s, re.I) for s in literals)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Constant):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                identifier = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else ''
                kind = credential_type(identifier, node.value.value)
                if kind:
                    add(node.lineno, kind, 'HIGH', 'Possible hardcoded credential in a string literal', 'Review the value; load real credentials from a secrets manager')
        if not isinstance(node, ast.Call):
            continue
        callee = name(node.func)
        if callee in ('eval', 'exec', 'builtins.eval', 'builtins.exec'):
            add(node.lineno, 'UNSAFE_EVAL', 'CRITICAL', f'Use of {callee}() can execute code', 'Avoid evaluating untrusted input; review its source')
        if callee in ('pickle.load', 'pickle.loads'):
            add(node.lineno, 'UNSAFE_DESERIALIZATION', 'HIGH', 'Loading pickle data can execute arbitrary code', 'Use a safer format for untrusted data')
        if isinstance(node.func, ast.Attribute) and node.func.attr in ('execute', 'executemany') and node.args and dynamic_sql(node.args[0]):
            add(node.lineno, 'SQL_INJECTION', 'CRITICAL', 'Dynamically constructed SQL reaches a database execution call', 'Use parameterized queries to keep data separate from SQL')
        shell = callee in ('os.system', 'os.popen') or (
            callee in ('subprocess.run', 'subprocess.call', 'subprocess.Popen', 'subprocess.check_call', 'subprocess.check_output')
            and any(k.arg == 'shell' and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords)
        )
        command = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == 'args'), None)
        if shell and command is not None and not isinstance(command, ast.Constant):
            add(node.lineno, 'COMMAND_INJECTION', 'CRITICAL', 'A dynamically constructed command is executed through a shell', 'Avoid shell=True; pass a validated argument list without a shell')
        if any(k.arg == 'usedforsecurity' and isinstance(k.value, ast.Constant) and k.value.value is False for k in node.keywords):
            continue
        algorithm = callee.rsplit('.', 1)[-1] if callee in ('hashlib.md5', 'hashlib.sha1') else None
        if callee == 'hashlib.new' and node.args and isinstance(node.args[0], ast.Constant):
            algorithm = str(node.args[0].value).lower()
        if algorithm in ('md5', 'sha1'):
            add(node.lineno, 'WEAK_HASH_' + algorithm.upper(), 'MEDIUM', 'Legacy hash called; review whether it protects security-sensitive data', 'Use a modern hash when collision resistance is required')
        if callee in ('Crypto.Cipher.DES.new', 'Cryptodome.Cipher.DES.new'):
            add(node.lineno, 'WEAK_CIPHER_DES', 'HIGH', 'DES encryption is requested', 'Use a modern authenticated encryption scheme')
    return issues
