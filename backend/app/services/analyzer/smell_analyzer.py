import ast
import re
from typing import List
from dataclasses import dataclass

@dataclass
class SmellIssue:
    file_path: str
    line: int
    issue_type: str
    severity: str
    message: str
    suggestion: str

def analyze_smells(
    file_path: str,
    content: str,
    language: str
) -> List[SmellIssue]:
    issues = []

    if language == "python":
        issues.extend(_analyze_python_smells(file_path, content))

    # Generic smells for all languages
    issues.extend(_analyze_generic_smells(file_path, content, language))

    return issues


def _analyze_python_smells(
    file_path: str,
    content: str
) -> List[SmellIssue]:
    issues = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return issues

    # Check for unused imports (basic detection)
    imported_names = set()
    used_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split('.')[0]
                imported_names.add((name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != '*':
                    name = alias.asname or alias.name
                    imported_names.add((name, node.lineno))
        elif isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    for name, line in imported_names:
        if name not in used_names and name != '__future__':
            issues.append(SmellIssue(
                file_path=file_path,
                line=line,
                issue_type="UNUSED_IMPORT",
                severity="LOW",
                message=f"Import '{name}' appears to be unused",
                suggestion=f"Remove unused import '{name}'"
            ))

    # Check for empty functions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            is_empty = (
                len(body) == 1 and
                isinstance(body[0], (ast.Pass, ast.Expr)) and
                (
                    isinstance(body[0], ast.Pass) or
                    isinstance(getattr(body[0], 'value', None), ast.Constant)
                )
            )
            if is_empty and node.name != '__init__':
                issues.append(SmellIssue(
                    file_path=file_path,
                    line=node.lineno,
                    issue_type="EMPTY_FUNCTION",
                    severity="LOW",
                    message=f"Function '{node.name}' has no implementation",
                    suggestion="Implement or remove the function"
                ))

    return issues


def _analyze_generic_smells(
    file_path: str,
    content: str,
    language: str
) -> List[SmellIssue]:
    issues = []
    lines = content.splitlines()

    # Check for TODO/FIXME/HACK comments
    todo_pattern = re.compile(
        r'#\s*(TODO|FIXME|HACK|XXX|BUG|WORKAROUND)',
        re.IGNORECASE
    )
    for i, line in enumerate(lines, 1):
        match = todo_pattern.search(line)
        if match:
            tag = match.group(1).upper()
            issues.append(SmellIssue(
                file_path=file_path,
                line=i,
                issue_type=f"TECHNICAL_DEBT_{tag}",
                severity="LOW",
                message=f"{tag} comment found: {line.strip()[:60]}",
                suggestion="Address or track this technical debt item"
            ))

    # Check for very long lines
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            issues.append(SmellIssue(
                file_path=file_path,
                line=i,
                issue_type="LONG_LINE",
                severity="LOW",
                message=f"Line {i} is {len(line)} characters long",
                suggestion="Keep lines under 120 characters"
            ))

    # Check for print statements in Python
    if language == "python":
        print_pattern = re.compile(r'^\s*print\s*\(')
        for i, line in enumerate(lines, 1):
            if print_pattern.match(line):
                issues.append(SmellIssue(
                    file_path=file_path,
                    line=i,
                    issue_type="DEBUG_PRINT",
                    severity="LOW",
                    message=f"print() statement found at line {i}",
                    suggestion="Use logging module instead of print()"
                ))

    return issues