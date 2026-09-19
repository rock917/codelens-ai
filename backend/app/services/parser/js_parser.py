import re
from app.services.parser.base_parser import BaseParser, ParsedFile, ParsedSymbol, ParsedImport

class JavaScriptParser(BaseParser):

    def parse(self, file_path: str, content: str) -> ParsedFile:
        is_ts = file_path.endswith(('.ts', '.tsx'))
        parsed = ParsedFile(
            path=file_path,
            language="typescript" if is_ts else "javascript"
        )

        lines = content.splitlines()
        parsed.loc = len(lines)

        self._extract_imports(content, parsed)
        self._extract_symbols(content, lines, parsed)

        parsed.num_classes = sum(1 for s in parsed.symbols if s.type == "class")
        parsed.num_functions = sum(
            1 for s in parsed.symbols if s.type in ("function", "method")
        )

        complexities = [s.complexity for s in parsed.symbols if s.complexity > 0]
        parsed.complexity_score = (
            round(sum(complexities) / len(complexities), 2)
            if complexities else 0.0
        )

        return parsed

    def _extract_imports(self, content: str, parsed: ParsedFile):
        # ES6 imports
        import_pattern = re.compile(
            r'import\s+(?:{[^}]+}|[\w*]+(?:\s*,\s*{[^}]+})?)\s+from\s+[\'"]([^\'"]+)[\'"]',
            re.MULTILINE
        )
        for i, line in enumerate(content.splitlines(), 1):
            match = import_pattern.search(line)
            if match:
                parsed.imports.append(ParsedImport(
                    module=match.group(1),
                    is_from_import=True,
                    line=i
                ))

        # require imports
        require_pattern = re.compile(
            r'(?:const|let|var)\s+\w+\s*=\s*require\([\'"]([^\'"]+)[\'"]\)'
        )
        for i, line in enumerate(content.splitlines(), 1):
            match = require_pattern.search(line)
            if match:
                parsed.imports.append(ParsedImport(
                    module=match.group(1),
                    is_from_import=False,
                    line=i
                ))

    def _extract_symbols(self, content: str, lines: list, parsed: ParsedFile):
        # Class declarations
        class_pattern = re.compile(
            r'^(?:export\s+)?(?:default\s+)?class\s+(\w+)',
            re.MULTILINE
        )
        for match in class_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            end_line = self._find_block_end(lines, line_num - 1)
            parsed.symbols.append(ParsedSymbol(
                name=match.group(1),
                type="class",
                start_line=line_num,
                end_line=end_line,
                signature=f"class {match.group(1)}"
            ))

        # Function declarations
        func_pattern = re.compile(
            r'^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
            re.MULTILINE
        )
        for match in func_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            end_line = self._find_block_end(lines, line_num - 1)
            complexity = self._calculate_complexity(
                '\n'.join(lines[line_num-1:end_line])
            )
            parsed.symbols.append(ParsedSymbol(
                name=match.group(1),
                type="function",
                start_line=line_num,
                end_line=end_line,
                signature=f"function {match.group(1)}({match.group(2)})",
                complexity=complexity
            ))

        # Arrow functions assigned to const/let
        arrow_pattern = re.compile(
            r'^(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
            re.MULTILINE
        )
        for match in arrow_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            end_line = self._find_block_end(lines, line_num - 1)
            parsed.symbols.append(ParsedSymbol(
                name=match.group(1),
                type="function",
                start_line=line_num,
                end_line=end_line,
                signature=f"const {match.group(1)} = () =>"
            ))

    def _find_block_end(self, lines: list, start_idx: int) -> int:
        depth = 0
        for i in range(start_idx, len(lines)):
            depth += lines[i].count('{') - lines[i].count('}')
            if depth <= 0 and i > start_idx:
                return i + 1
        return len(lines)

    def _calculate_complexity(self, code: str) -> float:
        complexity = 1
        patterns = [
            r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b',
            r'\bswitch\b', r'\bcatch\b', r'\b\?\b', r'\b&&\b', r'\b\|\|\b'
        ]
        for pattern in patterns:
            complexity += len(re.findall(pattern, code))
        return float(complexity)