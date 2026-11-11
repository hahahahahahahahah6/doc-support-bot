"""Deterministic document loading and portable JSON indexes."""
import json
import re
from pathlib import Path


def build_index(docs_dir):
    root = Path(docs_dir)
    if not root.is_dir():
        raise ValueError("Docs directory does not exist: " + str(root))
    chunks = []
    docs = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".md", ".txt"):
            continue
        doc = path.relative_to(root).as_posix()
        docs.append(doc)
        section = ""
        paragraph = []

        def flush():
            text = "\n".join(paragraph).strip()
            if text:
                chunks.append({"doc": doc, "section": section, "text": text})
            paragraph.clear()

        for line in path.read_text(encoding="utf-8").splitlines():
            heading = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line) if path.suffix.lower() == ".md" else None
            if heading:
                flush()
                section = heading.group(1)
            elif not line.strip():
                flush()
            else:
                paragraph.append(line)
        flush()
    return {"chunks": chunks, "docs": docs, "built_from": docs.copy()}


def load_index(path):
    with open(path, encoding="utf-8") as handle:
        index = json.load(handle)
    if not isinstance(index, dict) or not isinstance(index.get("chunks"), list):
        raise ValueError("Index must contain a chunks list")
    for chunk in index["chunks"]:
        if not isinstance(chunk, dict) or any(not isinstance(chunk.get(key), str) for key in ("doc", "section", "text")):
            raise ValueError("Invalid index chunk")
    return index
