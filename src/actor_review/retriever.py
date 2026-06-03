import re
from pathlib import Path


IMPORT_PATTERNS = {
    "rb": [r"require_relative\s+['\"](.+?)['\"]"],
    "py": [r"from\s+\.([^\s]+)\s+import", r"from\s+([^\s]+)\s+import"],
    "js": [r"from\s+['\"](\./[^'\"]+)['\"]", r"require\(['\"](\./[^'\"]+)['\"]\)"],
    "ts": [r"from\s+['\"](\./[^'\"]+)['\"]", r"require\(['\"](\./[^'\"]+)['\"]\)"],
    "go": [r"\"([^\"]+)\""],
    "java": [r"import\s+([\w\.]+);"],
}

SUFFIXES = {
    "rb": [".rb", ""],
    "py": [".py", "/__init__.py"],
    "js": [".js", ".ts", "/index.js"],
    "ts": [".ts", ".js", "/index.ts"],
    "go": [".go"],
    "java": [],
}


def find_fanout_files(filename: str, source_code: str, repo_path: str) -> list[dict]:
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    patterns = IMPORT_PATTERNS.get(ext, [])

    if not patterns:
        return []

    repo = Path(repo_path)
    source_dir = (repo / filename).parent
    results = []
    seen: set[str] = set()

    # only scan first 50 lines for imports
    header = "\n".join(source_code.splitlines()[:50])

    for pattern in patterns:
        for match in re.finditer(pattern, header):
            value = match.group(1)
            for suffix in SUFFIXES.get(ext, [""]):
                candidate = source_dir / (value + suffix)
                if candidate.exists():
                    rel = str(candidate.relative_to(repo))
                    if rel not in seen:
                        seen.add(rel)
                        try:
                            content = candidate.read_text(errors="replace")
                            results.append({
                                "file": rel,
                                "content": content[:2000],
                                "import": value,
                            })
                        except Exception:
                            continue
                    break

    return results
