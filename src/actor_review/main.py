import os
import sys

from actor_review.ast_extractor import extract_from_diff_files
from actor_review.blame import get_blame
from actor_review.pr import get_pr_data
from actor_review.retriever import find_fanout_files
from actor_review.review import review_diff
from actor_review.static_analysis import analyze_files, build_static_analysis_context


def build_context(pr_data, contexts, related_files: list[dict]) -> str:
    lines = []

    # PR metadata
    if pr_data.metadata:
        m = pr_data.metadata
        lines.append(f"## PR: {m.title}")
        if m.body:
            lines.append(f"### Description\n{m.body}")
        if m.commits:
            lines.append("### Commits\n" + "\n".join(f"- {c}" for c in m.commits))
        if m.comments:
            lines.append("### PR Comments\n" + "\n".join(f"- {c}" for c in m.comments))
        for issue in m.linked_issues:
            lines.append(f"### Linked Issue #{issue['number']}: {issue['title']}")
            if issue["body"]:
                lines.append(issue["body"])
            for c in issue["comments"]:
                lines.append(f"- {c}")

    # symbols
    for ctx in contexts:
        if not ctx.symbols:
            continue
        lines.append(f"## Symbols in {ctx.file}")
        for sym in ctx.symbols:
            lines.append(f"- {sym.kind} `{sym.name}` (line {sym.start_line}-{sym.end_line})")

    if related_files:
        lines.append("\n## Related Files (Fan-out)")
        for f in related_files:
            lines.append(f"### {f['file']}")
            lines.append(f["content"])

    return "\n".join(lines)


def build_blame_context(blame_results: dict[str, list]) -> str:
    lines = []
    for filename, blames in blame_results.items():
        if not blames:
            continue
        lines.append(f"## Git Blame: {filename}")
        for b in blames:
            lines.append(f"- [{b.sha}] {b.date} {b.author}: {b.message}")
            if b.pr_number:
                lines.append(f"  PR #{b.pr_number}: {b.pr_title}")
            if b.pr_body:
                lines.append(f"  説明: {b.pr_body}")
            for c in b.pr_comments:
                lines.append(f"  コメント: {c}")

    return "\n".join(lines)


def main():
    github_token = os.environ["ACTOR_REVIEW_GITHUB_TOKEN"]
    repo_name = sys.argv[1]
    pr_number = int(sys.argv[2])
    repo_path = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"Fetching PR data for {repo_name} #{pr_number}...")
    pr_data = get_pr_data(github_token, repo_name, pr_number)

    print("Extracting symbols...")
    files = [(f.filename, f.source_code) for f in pr_data.files]
    contexts = extract_from_diff_files(files)

    related_files = []
    if repo_path:
        print("Finding fan-out files...")
        for f in pr_data.files:
            related_files += find_fanout_files(f.filename, f.source_code, repo_path)
        print(f"Found {len(related_files)} fan-out files")

    blame_results = {}
    if repo_path:
        print("Running git blame...")
        for f in pr_data.files:
            blames = get_blame(f.filename, f.patch, repo_path, token=github_token, repo_name=repo_name)
            if blames:
                blame_results[f.filename] = blames
                print(f"  {f.filename}: {len(blames)} blames")
        print(f"Total blame entries: {sum(len(v) for v in blame_results.values())}")

    print("Running static analysis...")
    files_for_analysis = [(f.filename, f.source_code) for f in pr_data.files]
    static_findings = analyze_files(files_for_analysis)
    print(f"Static analysis: {len(static_findings)} findings")

    symbol_context = build_context(pr_data, contexts, related_files)
    blame_context = build_blame_context(blame_results)
    static_context = build_static_analysis_context(static_findings)

    print("Reviewing...")
    parts = [p for p in [symbol_context, blame_context, static_context, f"## Diff\n{pr_data.diff}"] if p]
    full_context = "\n\n".join(parts)
    result = review_diff(full_context)

    print("\n--- Review Result ---\n")
    print(result)


if __name__ == "__main__":
    main()
