from dataclasses import dataclass, field

import tree_sitter_go as ts_go
import tree_sitter_java as ts_java
import tree_sitter_javascript as ts_javascript
import tree_sitter_python as ts_python
import tree_sitter_ruby as ts_ruby
from tree_sitter import Language, Node, Parser


LANGUAGES = {
    "py": Language(ts_python.language()),
    "js": Language(ts_javascript.language()),
    "ts": Language(ts_javascript.language()),
    "java": Language(ts_java.language()),
    "go": Language(ts_go.language()),
    "rb": Language(ts_ruby.language()),
}

# node type -> symbol kind, per language extension
SYMBOL_TYPES: dict[str, dict[str, str]] = {
    "py":   {"function_definition": "function", "class_definition": "class"},
    "rb":   {"method": "method", "singleton_method": "method", "class": "class", "module": "class"},
    "js":   {"function_declaration": "function", "class_declaration": "class", "method_definition": "method"},
    "java": {"method_declaration": "method", "class_declaration": "class", "interface_declaration": "class"},
    "go":   {"function_declaration": "function", "method_declaration": "method"},
}
SYMBOL_TYPES["ts"] = SYMBOL_TYPES["js"]


@dataclass
class Symbol:
    name: str
    kind: str  # "function", "class", "method"
    file: str
    start_line: int
    end_line: int


@dataclass
class ExtractedContext:
    file: str
    symbols: list[Symbol] = field(default_factory=list)


def _walk(node: Node, ext: str, filename: str, symbols: list[Symbol]) -> None:
    kind = SYMBOL_TYPES.get(ext, {}).get(node.type)
    if kind:
        name_node = node.child_by_field_name("name")
        if name_node:
            symbols.append(Symbol(
                name=name_node.text.decode(),
                kind=kind,
                file=filename,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            ))

    for child in node.children:
        _walk(child, ext, filename, symbols)


def extract_symbols(filename: str, source_code: str) -> ExtractedContext:
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    language = LANGUAGES.get(ext)

    if language is None or not source_code:
        return ExtractedContext(file=filename)

    parser = Parser(language)
    tree = parser.parse(source_code.encode())
    symbols: list[Symbol] = []
    _walk(tree.root_node, ext, filename, symbols)

    return ExtractedContext(file=filename, symbols=symbols)


def extract_from_diff_files(files: list[tuple[str, str]]) -> list[ExtractedContext]:
    return [extract_symbols(filename, source) for filename, source in files]
