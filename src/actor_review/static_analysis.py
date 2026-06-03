import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


LANG_TO_RULESET = {
    "py": "p/python",
    "js": "p/javascript",
    "ts": "p/typescript",
    "java": "p/java",
    "go": "p/golang",
    "rb": "p/ruby",
}


@dataclass
class StaticFinding:
    rule_id: str
    path: str
    line: int
    message: str
    severity: str
    cwe: list[str] = field(default_factory=list)
    fix: str | None = None


def _run_opengrep(file_path: str, ruleset: str) -> list[dict]:
    try:
        proc = subprocess.run(
            ["opengrep", "scan", "--json", "--quiet", "--config", ruleset, file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    # opengrep exits non-zero when findings exist; parse stdout regardless
    try:
        # stdout may have scan summary lines before the JSON; find the JSON object
        stdout = proc.stdout.strip()
        json_start = stdout.find("{")
        if json_start == -1:
            return []
        data = json.loads(stdout[json_start:])
        return data.get("results", [])
    except (json.JSONDecodeError, ValueError):
        return []


def analyze_files(files: list[tuple[str, str]]) -> list[StaticFinding]:
    """Run static analysis on diff files. files is [(filename, source_code), ...]."""
    findings: list[StaticFinding] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for filename, source_code in files:
            if not source_code:
                continue

            ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
            ruleset = LANG_TO_RULESET.get(ext)
            if not ruleset:
                continue

            # Write source to a temp file preserving the original extension
            tmp_path = Path(tmpdir) / Path(filename).name
            try:
                tmp_path.write_text(source_code, encoding="utf-8")
            except Exception:
                continue

            for result in _run_opengrep(str(tmp_path), ruleset):
                extra = result.get("extra", {})
                metadata = extra.get("metadata", {})
                cwe = metadata.get("cwe", [])
                if isinstance(cwe, str):
                    cwe = [cwe]

                fix_val = extra.get("fix")

                findings.append(StaticFinding(
                    rule_id=result.get("check_id", ""),
                    path=filename,
                    line=result.get("start", {}).get("line", 0),
                    message=extra.get("message", ""),
                    severity=extra.get("severity", "INFO"),
                    cwe=cwe,
                    fix=fix_val if isinstance(fix_val, str) and fix_val else None,
                ))

    return findings


def build_static_analysis_context(findings: list[StaticFinding]) -> str:
    if not findings:
        return ""

    lines = ["## Static Analysis (Opengrep)"]
    for f in findings:
        lines.append(f"### [{f.severity}] {f.path}:{f.line} — {f.rule_id}")
        lines.append(f.message)
        if f.cwe:
            lines.append(f"CWE: {', '.join(f.cwe)}")
        if f.fix:
            lines.append(f"修正案: `{f.fix}`")

    return "\n".join(lines)
