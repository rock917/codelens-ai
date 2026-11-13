"""Syntax-tree extraction only: never runs a compiler, build tool, macro or user code."""
from functools import lru_cache
import importlib
from tree_sitter import Language, Parser
from app.services.parser.base_parser import BaseParser, ParsedFile, ParsedSymbol, ParsedImport

LANGUAGES = ('java', 'go', 'cpp')
TYPE_NODES = {
    'class_declaration': 'class', 'interface_declaration': 'interface',
    'enum_declaration': 'enum', 'record_declaration': 'record',
    'annotation_type_declaration': 'interface', 'class_specifier': 'class',
    'struct_specifier': 'struct', 'union_specifier': 'struct', 'enum_specifier': 'enum',
    'namespace_definition': 'namespace', 'alias_declaration': 'type',
}
CALLABLES = {'method_declaration', 'constructor_declaration', 'compact_constructor_declaration',
             'function_declaration', 'function_definition', 'method_elem'}
BRANCHES = {'if_statement', 'for_statement', 'enhanced_for_statement', 'for_range_loop',
            'while_statement', 'do_statement', 'catch_clause', 'case_statement',
            'expression_case', 'type_case', 'communication_case', 'switch_label',
            'ternary_expression', 'conditional_expression'}
NESTING = {'if_statement', 'for_statement', 'enhanced_for_statement', 'for_range_loop',
           'while_statement', 'do_statement', 'switch_statement', 'switch_expression',
           'expression_switch_statement', 'type_switch_statement', 'select_statement',
           'try_statement', 'catch_clause'}


@lru_cache(maxsize=3)
def grammar(language):
    return Language(importlib.import_module('tree_sitter_' + language).language())


def parse_tree(content, language):
    # Each thread gets its own mutable Parser; grammar objects are immutable.
    source = content.encode('utf-8')
    if len(source) > 1024 * 1024:
        raise ValueError('Source exceeds the 1 MiB parsing limit')
    # Go inserts a final semicolon at EOF, including files without a final newline.
    if language == 'go' and not source.endswith(b'\n'):
        source += b'\n'
    return source, Parser(grammar(language)).parse(source).root_node


def walk(root):
    stack = [root]
    visited = 0
    while stack:
        node = stack.pop()
        visited += 1
        if visited > 200000:
            raise ValueError('Source exceeds the syntax-tree node limit')
        yield node
        stack.extend(reversed(node.named_children))


def text(source, node):
    return source[node.start_byte:node.end_byte].decode('utf-8', errors='replace') if node else ''


def field(node, name):
    return node.child_by_field_name(name) if node else None


def end_line(node):
    return node.end_point.row + (1 if node.end_point.column else 0)


def declarator(node):
    """Unwrap pointer/reference declarators without mistaking parameters for names."""
    while node and field(node, 'declarator'):
        node = field(node, 'declarator')
    return node


def function_declarator(node):
    current = field(node, 'declarator')
    while current:
        if current.type == 'function_declarator':
            return current
        current = field(current, 'declarator')
    return None


def parent_name(source, node):
    current = node.parent
    while current:
        if current.type in TYPE_NODES or current.type == 'type_spec':
            name = field(current, 'name')
            if name:
                return text(source, name)
        current = current.parent
    return None


def metrics(body, source):
    if body is None:
        return 0, 0
    complexity, deepest = 1, 0
    stack = [(body, 0)]
    while stack:
        node, depth = stack.pop()
        # Nested functions/lambdas have their own control flow.
        if node != body and node.type in CALLABLES | {'lambda_expression', 'func_literal', 'class_declaration'}:
            continue
        if node.type in BRANCHES:
            complexity += 1
        if node.type == 'binary_expression' and any(c.type in ('&&', '||') for c in node.children):
            complexity += 1
        depth += int(node.type in NESTING)
        deepest = max(deepest, depth)
        stack.extend((child, depth) for child in node.named_children)
    return complexity, deepest


def callable_info(node, source, language):
    if node.type not in CALLABLES and not (language == 'cpp' and node.type in ('declaration', 'field_declaration')):
        return None
    if node.has_error:
        return None
    body, params = field(node, 'body'), field(node, 'parameters')
    name = field(node, 'name')
    parent = parent_name(source, node)
    kind = 'method' if node.type in ('method_declaration', 'method_elem', 'constructor_declaration', 'compact_constructor_declaration') else 'function'
    if language == 'cpp':
        decl = function_declarator(node)
        if decl is None:
            return None
        name, params = field(decl, 'declarator'), field(decl, 'parameters')
        # A function-pointer variable is not a function declaration.
        if name is None or name.type == 'parenthesized_declarator':
            return None
        if node.parent and node.parent.type == 'field_declaration_list':
            kind = 'method'
        if node.type == 'function_definition' and parent:
            current = node.parent
            while current and current.type not in TYPE_NODES:
                current = current.parent
            if current and current.type != 'namespace_definition':
                kind = 'method'
        if name.type == 'qualified_identifier':
            parent = text(source, field(name, 'scope')) or parent
            name = field(name, 'name')
    if name is None or name.is_missing:
        return None
    if language == 'go' and field(node, 'receiver'):
        receiver = field(node, 'receiver')
        receiver_type = field(receiver.named_children[0], 'type') if receiver.named_children else None
        while receiver_type and receiver_type.type in ('pointer_type', 'generic_type'):
            receiver_type = field(receiver_type, 'type') or receiver_type.named_children[0]
        parent = text(source, receiver_type)
    count = 0
    if params:
        for param in params.named_children:
            if param.type in ('comment', 'line_comment', 'block_comment'):
                continue
            if language == 'go':
                count += max(1, len(param.children_by_field_name('name')))
            elif text(source, param).strip() != 'void':
                count += 1
    start_node = node.parent if node.parent and node.parent.type == 'template_declaration' else node
    signature_end = body.start_byte if body else node.end_byte
    signature = ' '.join(source[start_node.start_byte:signature_end].decode('utf-8').split())[:1000].rstrip(';')
    complexity, nesting = metrics(body, source)
    previous = node.prev_named_sibling
    doc = text(source, previous)[:4000] if previous and 'comment' in previous.type and node.start_point.row - previous.end_point.row <= 1 else None
    symbol = ParsedSymbol(text(source, name), kind, start_node.start_point.row + 1, max(node.start_point.row + 1, end_line(node)),
                          parent_name=parent, signature=signature, docstring=doc, complexity=float(complexity))
    return symbol, body, count, nesting


class CompiledParser(BaseParser):
    def __init__(self, language):
        self.language = language

    def parse(self, file_path, content):
        source, root = parse_tree(content, self.language)
        parsed = ParsedFile(path=file_path, language=self.language, loc=len(content.splitlines()))
        if root.has_error:
            errors = [n for n in walk(root) if n.type == 'ERROR' or n.is_missing]
            lines = ', '.join(str(n.start_point.row + 1) for n in errors[:5])
            parsed.diagnostics.append(f'Partial syntax parse near line(s) {lines or "unknown"}. Source remains searchable; this file is excluded from health scoring.')
        for node in walk(root):
            kind = TYPE_NODES.get(node.type)
            name = field(node, 'name')
            if self.language == 'go' and node.type in ('type_spec', 'type_alias'):
                kind = {'struct_type': 'struct', 'interface_type': 'interface'}.get(getattr(field(node, 'type'), 'type', ''), 'type')
            if kind and name and not name.is_missing:
                start_node = node.parent if node.parent and node.parent.type == 'template_declaration' else node
                body = field(node, 'body') or field(node, 'type')
                stop = body.start_byte if body else node.end_byte
                parsed.symbols.append(ParsedSymbol(text(source, name), kind, start_node.start_point.row + 1,
                    max(node.start_point.row + 1, end_line(node)), parent_name=parent_name(source, node),
                    signature=' '.join(source[start_node.start_byte:stop].decode('utf-8').split())[:1000]))
            info = callable_info(node, source, self.language)
            if info:
                parsed.symbols.append(info[0])
            if node.type == 'import_declaration' and self.language == 'java':
                module = text(source, node).removeprefix('import ').removeprefix('static ').rstrip(';').strip()
                parsed.imports.append(ParsedImport(module, line=node.start_point.row + 1))
            elif node.type == 'import_spec' and self.language == 'go':
                module = text(source, field(node, 'path')).strip('"`')
                alias = text(source, field(node, 'name')) or module.rsplit('/', 1)[-1]
                parsed.imports.append(ParsedImport(module, names=[alias], line=node.start_point.row + 1))
            elif node.type == 'preproc_include' and self.language == 'cpp':
                parsed.imports.append(ParsedImport(text(source, field(node, 'path')).strip('<>"'), line=node.start_point.row + 1))
        local_types = {s.name for s in parsed.symbols if s.type in ('class', 'struct', 'interface', 'enum', 'record')}
        for symbol in parsed.symbols:
            if symbol.type == 'function' and (symbol.parent_name or '').split('<', 1)[0] in local_types:
                symbol.type = 'method'
        parsed.num_classes = sum(s.type in ('class', 'struct', 'interface', 'enum', 'record') for s in parsed.symbols)
        parsed.num_functions = sum(s.type in ('function', 'method') for s in parsed.symbols)
        values = [s.complexity for s in parsed.symbols if s.complexity > 0]
        parsed.complexity_score = round(sum(values) / len(values), 2) if values else 0
        # Use bounded, symbol-labelled chunks, including short import/header gaps.
        # Original source line numbers are preserved, including for partial parses.
        parsed.display_content = content
        covered = set()
        for symbol in parsed.symbols:
            parsed.sections.append(dict(name=symbol.name, type=symbol.type, parent_name=symbol.parent_name,
                language=self.language, start_line=symbol.start_line, end_line=symbol.end_line))
            covered.update(range(symbol.start_line, symbol.end_line + 1))
        start = None
        for line in range(1, parsed.loc + 2):
            if line <= parsed.loc and line not in covered:
                if start is None:
                    start = line
            elif start is not None:
                parsed.sections.append(dict(name='Module source', type='module_level', language=self.language,
                    start_line=start, end_line=line - 1))
                start = None
        return parsed
