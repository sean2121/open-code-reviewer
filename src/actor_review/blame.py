import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime

from github import Github


@dataclass
class BlameCommit:
    sha: str
    author: str
    date: str
    message: str
    pr_number: int | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    pr_comments: list[str] = field(default_factory=list)


def _extract_changed_lines(patch: str) -> list[tuple[int, int]]:
    ranges = []
    for match in re.finditer(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", patch):
        start = int(match.group(1))
        count = int(match.group(2)) if match.group(2) else 1
        if count > 0:
            ranges.append((start, start + count - 1))
    return ranges


def _run_blame(filename: str, start: int, end: int, repo_path: str) -> list[dict]:
    try:
        proc = subprocess.run(
            ["git", "blame", "-p", f"-L{start},{end}", filename],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return []

    results = []
    seen_shas: set[str] = set()
    current_sha = None
    current_line = None
    author = ""
    date = ""
    message = ""

    for line in proc.stdout.splitlines():
        sha_match = re.match(r"^([0-9a-f]{40})\s+\d+\s+(\d+)", line)
        if sha_match:
            current_sha = sha_match.group(1)
            current_line = int(sha_match.group(2))
            author = ""
            date = ""
            message = ""
            continue

        if line.startswith("author ") and not line.startswith("author-"):
            author = line[7:]
        elif line.startswith("author-time "):
            date = datetime.fromtimestamp(int(line[12:])).strftime("%Y-%m-%d")
        elif line.startswith("summary "):
            message = line[8:]
            if current_sha and current_sha not in seen_shas:
                seen_shas.add(current_sha)
                results.append({
                    "sha": current_sha,
                    "line": current_line,
                    "author": author,
                    "date": date,
                    "message": message,
                })

    return results


def _fetch_pr_for_commit(repo, sha: str) -> dict | None:
    try:
        prs = list(repo.get_commit(sha).get_pulls())
        if not prs:
            return None
        pr = prs[0]
        comments = [
            f"{c.user.login}: {c.body[:200]}"
            for c in pr.get_issue_comments()
        ][:5]
        return {
            "number": pr.number,
            "title": pr.title,
            "body": (pr.body or "")[:500],
            "comments": comments,
        }
    except Exception:
        return None


def get_blame(filename: str, patch: str, repo_path: str, token: str | None = None, repo_name: str | None = None) -> list[BlameCommit]:
    ranges = _extract_changed_lines(patch)
    if not ranges:
        return []

    raw_blames = []
    for start, end in ranges[:3]:
        raw_blames += _run_blame(filename, start, end, repo_path)

    if not raw_blames:
        return []

    # fetch PR info for each unique SHA
    pr_cache: dict[str, dict | None] = {}
    repo = None
    if token and repo_name:
        try:
            repo = Github(token).get_repo(repo_name)
        except Exception:
            pass

    results = []
    for b in raw_blames:
        sha = b["sha"]
        if sha not in pr_cache:
            pr_cache[sha] = _fetch_pr_for_commit(repo, sha) if repo else None
        pr = pr_cache[sha]

        results.append(BlameCommit(
            sha=sha[:8],
            author=b["author"],
            date=b["date"],
            message=b["message"],
            pr_number=pr["number"] if pr else None,
            pr_title=pr["title"] if pr else None,
            pr_body=pr["body"] if pr else None,
            pr_comments=pr["comments"] if pr else [],
        ))

    return results
