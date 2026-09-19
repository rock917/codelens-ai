import ast
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class ComplexityIssue:
    file_path: str
    symbol_name: str
    symbol_type: str
    line: int
    issue_type: str
    severity: str
    message: str
    suggestion: str

def analyze_complexity(
    file_path: str,
    content: str,
    language: str
) -> List[ComplexityIssue]:
    issues = []
    if language != "python":
        return issues

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check function length
            func_length = (
                getattr(node, 'end_lineno', node.lineno) - node.lineno
            )
            if func_length > 50:
                severity = "HIGH" if func_length > 100 else "MEDIUM"
                issues.append(ComplexityIssue(
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="function",
                    line=node.lineno,
                    issue_type="LONG_FUNCTION",
                    severity=severity,
                    message=f"Function '{node.name}' is {func_length} lines long",
                    suggestion="Break into smaller focused functions"
                ))

            # Check parameter count
            param_count = len(node.args.args)
            if param_count > 5:
                severity = "HIGH" if param_count > 8 else "MEDIUM"
                issues.append(ComplexityIssue(
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="function",
                    line=node.lineno,
                    issue_type="TOO_MANY_PARAMS",
                    severity=severity,
                    message=f"Function '{node.name}' has {param_count} parameters",
                    suggestion="Consider using a config object or dataclass"
                ))

            # Check cyclomatic complexity
            complexity = _calculate_complexity(node)
            if complexity > 10:
                severity = "HIGH" if complexity > 15 else "MEDIUM"
                issues.append(ComplexityIssue(
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="function",
                    line=node.lineno,
                    issue_type="HIGH_COMPLEXITY",
                    severity=severity,
                    message=f"Function '{node.name}' has cyclomatic complexity of {complexity}",
                    suggestion="Simplify logic, extract helper functions"
                ))

            # Check nesting depth
            depth = _get_max_nesting(node)
            if depth > 4:
                severity = "HIGH" if depth > 6 else "MEDIUM"
                issues.append(ComplexityIssue(
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="function",
                    line=node.lineno,
                    issue_type="DEEP_NESTING",
                    severity=severity,
                    message=f"Function '{node.name}' has nesting depth of {depth}",
                    suggestion="Use early returns or extract nested logic"
                ))

        elif isinstance(node, ast.ClassDef):
            # Check class size
            class_length = (
                getattr(node, 'end_lineno', node.lineno) - node.lineno
            )
            method_count = sum(
                1 for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            if class_length > 200:
                issues.append(ComplexityIssue(
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="class",
                    line=node.lineno,
                    issue_type="LARGE_CLASS",
                    severity="MEDIUM",
                    message=f"Class '{node.name}' is {class_length} lines long",
                    suggestion="Consider splitting into smaller classes"
                ))
            if method_count > 15:
                issues.append(ComplexityIssue(
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="class",
                    line=node.lineno,
                    issue_type="TOO_MANY_METHODS",
                    severity="MEDIUM",
                    message=f"Class '{node.name}' has {method_count} methods",
                    suggestion="Consider splitting responsibilities"
                ))

    return issues


def _calculate_complexity(node) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (
            ast.If, ast.While, ast.For, ast.ExceptHandler,
            ast.With, ast.Assert, ast.comprehension,
            ast.AsyncFor, ast.AsyncWith
        )):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def _get_max_nesting(node, current_depth=0) -> int:
    max_depth = current_depth
    nesting_nodes = (
        ast.If, ast.For, ast.While, ast.With,
        ast.Try, ast.AsyncFor, ast.AsyncWith
    )
    for child in ast.iter_child_nodes(node):
        if isinstance(child, nesting_nodes):
            depth = _get_max_nesting(child, current_depth + 1)
            max_depth = max(max_depth, depth)
        else:
            depth = _get_max_nesting(child, current_depth)
            max_depth = max(max_depth, depth)
    return max_depth