from pathlib import Path

from litellm import completion

from open_code_reviewer.config import REVIEW_MODEL

SYSTEM_PROMPT = """You are an expert code reviewer. Analyze the given pull request information and provide feedback.

## Available context
- PR title, description, commit messages: use to understand the intent of the change
- Git blame: use to understand when, by whom, and why the changed lines were originally written
- Code diff: the actual changes

## Review criteria
- Security vulnerabilities
- Logic errors and bugs
- Code style and readability
- Consistency with past implementation intent

## Output format
Respond with a JSON array of findings. Each finding must have:
- "file": file path (string)
- "line": line number in the file (integer)
- "severity": "high", "medium", or "low" (string)
- "message": description of the problem and suggested fix (string)

Example:
[
  {
    "file": "src/foo.py",
    "line": 42,
    "severity": "high",
    "message": "SQL query uses string interpolation with user input, risking SQL injection. Use parameterized queries instead."
  }
]

If there are no issues, return an empty array: []
Only report issues you are highly confident about. Avoid noise. Output JSON only, no other text."""

INSTRUCTIONS_DIR = Path(__file__).parent.parent.parent / "instructions"


def _load_instructions() -> str:
    if not INSTRUCTIONS_DIR.is_dir():
        return ""
    parts = []
    for path in sorted(INSTRUCTIONS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _build_system_prompt() -> str:
    extra = _load_instructions()
    if not extra:
        return SYSTEM_PROMPT
    return f"{SYSTEM_PROMPT}\n\n## Additional review instructions\n\n{extra}"


def review_diff(diff: str, model: str = REVIEW_MODEL) -> list[dict]:
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": f"Review the following diff:\n\n{diff}"},
        ],
        max_tokens=4096,
        response_format={"type": "json_object"},
    )

    import json
    raw = response.choices[0].message.content
    parsed = json.loads(raw)
    # handle both {"findings": [...]} and plain [...]
    if isinstance(parsed, list):
        return parsed
    return parsed.get("findings", list(parsed.values())[0] if parsed else [])
