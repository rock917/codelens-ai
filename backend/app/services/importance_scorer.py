from typing import List
from app.services.parser.base_parser import ParsedFile, ParsedImport

# Keywords that indicate high importance files
HIGH_IMPORTANCE_KEYWORDS = {
    "auth", "authentication", "authorization", "security",
    "database", "db", "connection", "model", "schema",
    "main", "app", "server", "index", "config", "settings",
    "api", "router", "routes", "middleware", "gateway",
    "payment", "billing", "user", "admin"
}

MEDIUM_IMPORTANCE_KEYWORDS = {
    "service", "handler", "controller", "manager",
    "util", "utils", "helper", "helpers", "common",
    "base", "core", "shared", "constants"
}

def calculate_importance_score(
    parsed_file: ParsedFile,
    all_files: List[str],
    dependent_count: int = 0
) -> tuple[float, str]:
    score = 0.0
    path_lower = parsed_file.path.lower()
    filename = path_lower.split('/')[-1].replace('.py', '').replace('.js', '').replace('.ts', '')

    # 1. Keyword match in path (0-30 points)
    for keyword in HIGH_IMPORTANCE_KEYWORDS:
        if keyword in path_lower:
            score += 30
            break

    for keyword in MEDIUM_IMPORTANCE_KEYWORDS:
        if keyword in path_lower:
            score += 15
            break

    # 2. Entry point detection (0-25 points)
    entry_points = {"main", "index", "app", "server", "manage", "wsgi", "asgi"}
    if filename in entry_points:
        score += 25

    # 3. Number of symbols (0-20 points)
    symbol_count = len(parsed_file.symbols)
    score += min(symbol_count * 2, 20)

    # 4. Dependents (files that import this file) (0-20 points)
    score += min(dependent_count * 5, 20)

    # 5. Complexity (0-10 points)
    if parsed_file.complexity_score > 5:
        score += 10
    elif parsed_file.complexity_score > 2:
        score += 5

    # 6. Number of imports (shows connectivity) (0-10 points)
    score += min(len(parsed_file.imports) * 2, 10)

    # Normalize to 0-100
    score = min(score, 100)

    # Classify
    if score >= 60:
        level = "HIGH"
    elif score >= 30:
        level = "MEDIUM"
    else:
        level = "LOW"

    return round(score, 2), level