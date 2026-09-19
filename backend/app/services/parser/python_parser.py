import ast
from typing import List, Optional
from app.services.parser.base_parser import BaseParser, ParsedFile, ParsedSymbol, ParsedImport

class PythonParser(BaseParser):

    def parse(self, file_path: str, content: str) -> ParsedFile:
        parsed = ParsedFile(
            path=file_path,
            language="python"
        )

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            parsed.error = str(e)
            return parsed

        lines = content.splitlines()
        parsed.loc = len(lines)

        for node in ast.walk(tree):
            # Extract imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parsed.imports.append(ParsedImport(
                        module=alias.name,
                        names=[alias.asname or alias.name],
                        is_from_import=False,
                        line=node.lineno
                    ))

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                parsed.imports.append(ParsedImport(
                    module=module,
                    names=names,
                    is_from_import=True,
                    line=node.lineno
                ))

        # Extract classes and functions (top level + nested)
        self._extract_symbols(tree, parsed, parent_name=None)

        parsed.num_classes = sum(
            1 for s in parsed.symbols if s.type == "class"
        )
        parsed.num_functions = sum(
            1 for s in parsed.symbols if s.type in ("function", "method")
        )

        # Overall complexity = average of all function complexities
        complexities = [s.complexity for s in parsed.symbols if s.complexity > 0]
        parsed.complexity_score = (
            round(sum(complexities) / len(complexities), 2)
            if complexities else 0.0
        )

        return parsed

    def _extract_symbols(self, tree, parsed: ParsedFile, parent_name: Optional[str]):
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node) or ""
                decorators = [
                    self._get_decorator_name(d) for d in node.decorator_list
                ]
                symbol = ParsedSymbol(
                    name=node.name,
                    type="class",
                    start_line=node.lineno,
                    end_line=getattr(node, 'end_lineno', node.lineno),
                    parent_name=parent_name,
                    signature=f"class {node.name}",
                    docstring=docstring,
                    decorators=decorators
                )
                parsed.symbols.append(symbol)
                # Recurse into class body
                self._extract_symbols(node, parsed, parent_name=node.name)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node) or ""
                decorators = [
                    self._get_decorator_name(d) for d in node.decorator_list
                ]
                symbol_type = "method" if parent_name else "function"
                complexity = self._calculate_complexity(node)
                signature = self._get_signature(node)

                symbol = ParsedSymbol(
                    name=node.name,
                    type=symbol_type,
                    start_line=node.lineno,
                    end_line=getattr(node, 'end_lineno', node.lineno),
                    parent_name=parent_name,
                    signature=signature,
                    docstring=docstring,
                    complexity=complexity,
                    decorators=decorators
                )
                parsed.symbols.append(symbol)

    def _get_signature(self, node) -> str:
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(args)})"

    def _get_decorator_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{node.value.id}.{node.attr}"
        return ""

    def _calculate_complexity(self, node) -> float:
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
        return float(complexity)