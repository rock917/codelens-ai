from app.services.parser.base_parser import BaseParser, ParsedFile
from app.services.parser.python_parser import PythonParser
from app.services.parser.js_parser import JavaScriptParser

class ParserFactory:
    _parsers = {
        "python": PythonParser(),
        "javascript": JavaScriptParser(),
        "typescript": JavaScriptParser(),
    }

    @classmethod
    def get_parser(cls, language: str) -> BaseParser:
        return cls._parsers.get(language.lower())

    @classmethod
    def parse_file(cls, file_path: str, content: str, language: str) -> ParsedFile:
        parser = cls.get_parser(language)
        if not parser:
            from app.services.parser.base_parser import ParsedFile
            return ParsedFile(
                path=file_path,
                language=language,
                error=f"No parser for language: {language}"
            )
        return parser.safe_parse(file_path, content)