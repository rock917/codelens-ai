from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ParsedSymbol:
    name: str
    type: str  # class, function, method, variable
    start_line: int
    end_line: int
    parent_name: Optional[str] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None
    complexity: float = 0.0
    decorators: List[str] = field(default_factory=list)

@dataclass
class ParsedImport:
    module: str
    names: List[str] = field(default_factory=list)
    is_from_import: bool = False
    line: int = 0

@dataclass
class ParsedFile:
    path: str
    language: str
    symbols: List[ParsedSymbol] = field(default_factory=list)
    imports: List[ParsedImport] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    loc: int = 0
    complexity_score: float = 0.0
    num_classes: int = 0
    num_functions: int = 0
    error: Optional[str] = None

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str, content: str) -> ParsedFile:
        pass

    def safe_parse(self, file_path: str, content: str) -> ParsedFile:
        try:
            return self.parse(file_path, content)
        except Exception as e:
            return ParsedFile(
                path=file_path,
                language="unknown",
                error=str(e)
            )