import re
from dataclasses import dataclass, field

from github import Github


@dataclass
class PRFile:
    filename: str
    patch: str
    source_code: str


@dataclass
class PRMetadata:
    title: str
    body: str
    commits: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    linked_issues: list[dict] = field(default_factory=list)


@dataclass
class PRData:
    diff: str
    metadata: PRMetadata = None
    files: list[PRFile] = field(default_factory=list)


def _extract_issue_numbers(text: str) -> list[int]:
    # extract issue numbers from "closes #123", "fixes #456" etc.
    pattern = r"(?:closes?|fixes?|resolves?)\s+#(\d+)"
    return [int(n) for n in re.findall(pattern, text, re.IGNORECASE)]


def get_pr_data(token: str, repo_name: str, pr_number: int) -> PRData:
    gh = Github(token)
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    # commits
    commits = [
        c.commit.message.splitlines()[0]
        for c in pr.get_commits()
    ]

    # PR comments
    comments = [
        f"{c.user.login}: {c.body[:300]}"
        for c in pr.get_issue_comments()
    ]

    # linked issues
    linked_issues = []
    body = pr.body or ""
    for issue_number in _extract_issue_numbers(body):
        try:
            issue = repo.get_issue(issue_number)
            issue_comments = [
                f"{c.user.login}: {c.body[:200]}"
                for c in issue.get_comments()
            ][:5]
            linked_issues.append({
                "number": issue_number,
                "title": issue.title,
                "body": (issue.body or "")[:500],
                "comments": issue_comments,
            })
        except Exception:
            continue

    metadata = PRMetadata(
        title=pr.title,
        body=body[:1000],
        commits=commits,
        comments=comments[:10],
        linked_issues=linked_issues,
    )

    # diff and file contents
    diff_parts = []
    files = []

    for file in pr.get_files():
        if not file.patch:
            continue

        diff_parts.append(f"### {file.filename}\n{file.patch}")

        try:
            content = repo.get_contents(file.filename, ref=pr.head.sha)
            source_code = content.decoded_content.decode("utf-8", errors="replace")
        except Exception:
            source_code = ""

        files.append(PRFile(
            filename=file.filename,
            patch=file.patch,
            source_code=source_code,
        ))

    return PRData(
        diff="\n\n".join(diff_parts),
        metadata=metadata,
        files=files,
    )
