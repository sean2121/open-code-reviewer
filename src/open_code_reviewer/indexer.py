from pathlib import Path

import lancedb
from sentence_transformers import SentenceTransformer

from open_code_reviewer.ast_extractor import Symbol, extract_symbols


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TABLE_NAME = "symbols"

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def index_repository(repo_path: str, db_path: str = ".lancedb") -> None:
    repo = Path(repo_path)
    db = lancedb.connect(db_path)

    model = _get_model()
    rows = []

    extensions = {".py", ".rb", ".js", ".ts", ".java", ".go"}
    for file_path in repo.rglob("*"):
        if file_path.suffix not in extensions:
            continue
        if any(p in file_path.parts for p in ["node_modules", ".git", "vendor", "tmp"]):
            continue

        try:
            source = file_path.read_text(errors="replace")
        except Exception:
            continue

        ctx = extract_symbols(str(file_path.relative_to(repo)), source)
        for sym in ctx.symbols:
            text = f"{sym.kind} {sym.name} in {sym.file}"
            rows.append({
                "text": text,
                "name": sym.name,
                "kind": sym.kind,
                "file": sym.file,
                "start_line": sym.start_line,
                "end_line": sym.end_line,
            })

    if not rows:
        return

    embeddings = model.encode([r["text"] for r in rows], show_progress_bar=True)
    for row, emb in zip(rows, embeddings):
        row["vector"] = emb.tolist()

    if TABLE_NAME in db.table_names():
        db.drop_table(TABLE_NAME)

    db.create_table(TABLE_NAME, rows)
    print(f"Indexed {len(rows)} symbols from {repo_path}")
