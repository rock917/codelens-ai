"""Limited syntax-based checks, not compiler, dependency or data-flow analysis."""
import re
from app.services.parser.compiled_parser import parse_tree, walk, text, field, declarator, callable_info
from app.services.analyzer.smell_analyzer import SmellIssue


def analyze_compiled(path, content, language):
    source, root = parse_tree(content, language)
    if root.has_error:
        return [], 'Syntax could not be parsed completely; excluded from health scoring. Source is still searchable.'
    issues = []
    seen = set()
    def add(node, category, severity, message, suggestion):
        key = (node.start_byte, category)
        if key in seen:
            return
        seen.add(key)
        issues.append(SmellIssue(path, node.start_point.row + 1, category, severity, message, suggestion))

    aliases = {}
    nodes = list(walk(root))
    for node in nodes:
        if node.type == 'import_spec':
            module = text(source, field(node, 'path')).strip('"`')
            aliases[text(source, field(node, 'name')) or module.rsplit('/', 1)[-1]] = module
    for node in nodes:
        info = callable_info(node, source, language)
        if info and info[1] is not None:
            symbol, body, parameters, nesting = info
            length = symbol.end_line - symbol.start_line + 1
            if length > 50:
                add(node, 'LONG_FUNCTION', 'HIGH' if length > 100 else 'MEDIUM',
                    f"Function '{symbol.name}' spans {length} lines", 'Extract smaller focused functions')
            if parameters > 5:
                add(node, 'TOO_MANY_PARAMS', 'HIGH' if parameters > 8 else 'MEDIUM',
                    f"Function '{symbol.name}' has {parameters} parameters", 'Group related arguments into a configuration type')
            if symbol.complexity > 10:
                add(node, 'HIGH_COMPLEXITY', 'HIGH' if symbol.complexity > 15 else 'MEDIUM',
                    f"Function '{symbol.name}' has estimated cyclomatic complexity {int(symbol.complexity)}", 'Extract helpers and simplify branches')
            if nesting > 4:
                add(node, 'DEEP_NESTING', 'HIGH' if nesting > 6 else 'MEDIUM',
                    f"Function '{symbol.name}' has nesting depth {nesting}", 'Use early returns or extract nested logic')
        if 'comment' in node.type:
            match = re.search(r'\b(TODO|FIXME|HACK|XXX|BUG|WORKAROUND)\b', text(source, node), re.I)
            if match:
                tag = match.group(1).upper()
                add(node, 'TECHNICAL_DEBT_' + tag, 'LOW', f'{tag} comment found', 'Address or track this technical debt')

        pairs = []
        if node.type in ('variable_declarator', 'init_declarator'):
            pairs = [(field(node, 'name') or declarator(field(node, 'declarator')), field(node, 'value'))]
        elif language == 'go' and node.type in ('short_var_declaration', 'assignment_statement', 'var_spec', 'const_spec'):
            left = field(node, 'left')
            right = field(node, 'right') or field(node, 'value')
            names = left.named_children if left else node.children_by_field_name('name')
            values = right.named_children if right else []
            if len(names) == len(values):
                pairs = zip(names, values)
        for name, value in pairs:
            if value is None or value.type not in ('string_literal', 'raw_string_literal', 'interpreted_string_literal', 'text_block'):
                continue
            identifier = text(source, name).rsplit('.', 1)[-1]
            if re.fullmatch(r'(?:\w+_)?(?:password|passwd|pwd|secret|secret_key|api_key|apikey|token|access_token)', identifier, re.I) and len(text(source, value).strip('"`')) >= 4:
                add(node, 'HARDCODED_CREDENTIAL', 'HIGH', 'Possible hardcoded credential in a string literal', 'Review the value; load credentials from a secrets manager')

        if language == 'cpp' and node.type == 'call_expression':
            name = text(source, field(node, 'function'))
            if name.removeprefix('std::').removeprefix('::') in ('gets', 'strcpy', 'strcat', 'sprintf'):
                add(node, 'UNBOUNDED_BUFFER_OPERATION', 'HIGH', f'{name} does not enforce the destination buffer capacity', 'Prefer bounded operations or standard string containers; verify buffer capacity')
        if language == 'go' and node.type == 'call_expression':
            func = field(node, 'function')
            if func and func.type == 'selector_expression':
                package = aliases.get(text(source, field(func, 'operand')))
                method = text(source, field(func, 'field'))
                if (package in ('crypto/md5', 'crypto/sha1') and method in ('New', 'Sum')) or (package == 'crypto/des' and method in ('NewCipher', 'NewTripleDESCipher')):
                    add(node, 'WEAK_CRYPTO', 'MEDIUM', f'Legacy cryptographic primitive from {package}; review its security purpose', 'Use modern cryptography when collision resistance or confidentiality is required')
        if language == 'java' and node.type == 'method_invocation':
            owner = text(source, field(node, 'object'))
            method = text(source, field(node, 'name'))
            args = field(node, 'arguments')
            literals = [text(source, c).strip('"').upper() for c in args.named_children if c.type == 'string_literal'] if args else []
            if method == 'getInstance' and owner in ('MessageDigest', 'java.security.MessageDigest', 'Cipher', 'javax.crypto.Cipher') and any(v in ('MD5', 'SHA-1', 'SHA1', 'DES', 'RC4') or v.startswith('DES/') for v in literals):
                add(node, 'WEAK_CRYPTO', 'MEDIUM', 'Legacy cryptographic algorithm requested; review its security purpose', 'Use modern cryptography appropriate to the use case')
    return issues, None
