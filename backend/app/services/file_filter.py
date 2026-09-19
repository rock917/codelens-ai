import os
from pathlib import Path
from typing import Set

# Directories to completely ignore
IGNORED_DIRS: Set[str] = {
    "node_modules", ".git", "__pycache__", "dist", "build",
    "target", "coverage", "vendor", ".venv", "venv", "env",
    ".env", "eggs", ".eggs", "wheels", "htmlcov", ".tox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".next", ".nuxt", "out", ".svelte-kit",
    "bin", "obj", "Debug", "Release",
    ".idea", ".vscode", "__MACOSX"
}

# File extensions to process (source code)
SUPPORTED_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".rb", ".php", ".cs",
    ".swift", ".kt", ".scala", ".r", ".sql"
}

# Config/doc files to keep even though not source code
USEFUL_CONFIG_FILES: Set[str] = {
    "package.json", "pyproject.toml", "requirements.txt",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "tsconfig.json", "readme.md", "readme.rst", "readme.txt",
    ".env.example", "makefile", "setup.py", "setup.cfg",
    "cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "webpack.config.js", "vite.config.ts", "vite.config.js"
}

# Extensions to always skip
IGNORED_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".mp4", ".mp3", ".avi", ".mov", ".wav",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".lock", ".sum", ".snap",
    ".min.js", ".min.css",
    ".map", ".d.ts",
    ".pyc", ".pyo", ".pyd",
    ".class", ".jar",
    ".woff", ".woff2", ".ttf", ".eot"
}

# Max file size to process (1MB)
MAX_FILE_SIZE = 1 * 1024 * 1024

def should_process_file(file_path: str) -> bool:
    path = Path(file_path)
    
    # Check ignored directories in path
    for part in path.parts:
        if part.lower() in {d.lower() for d in IGNORED_DIRS}:
            return False
    
    filename = path.name.lower()
    extension = path.suffix.lower()
    
    # Check if it's a useful config file
    if filename in USEFUL_CONFIG_FILES:
        return True
    
    # Check ignored extensions
    if extension in IGNORED_EXTENSIONS:
        return False
    
    # Check if extension ends with ignored
    for ignored_ext in IGNORED_EXTENSIONS:
        if filename.endswith(ignored_ext):
            return False
    
    # Check supported extensions
    if extension in SUPPORTED_EXTENSIONS:
        return True
    
    return False

def detect_language(file_path: str) -> str:
    extension_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".r": "r",
        ".sql": "sql",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".rst": "rst"
    }
    ext = Path(file_path).suffix.lower()
    return extension_map.get(ext, "unknown")

def is_binary_file(file_path: str) -> bool:
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(8192)
            if b'\x00' in chunk:
                return True
        return False
    except Exception:
        return True

def get_file_size(file_path: str) -> int:
    try:
        return os.path.getsize(file_path)
    except Exception:
        return 0