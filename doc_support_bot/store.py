"""Local JSONL persistence and CSV export."""
import csv
import json
from datetime import datetime, timezone
from threading import RLock

_LOCK = RLock()


def log_qa(path, record):
    entry = {key: record[key] for key in ("question", "answer", "escalated", "sources")}
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with _LOCK, open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_log(path):
    if path is None:
        return []
    try:
        with _LOCK, open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    except FileNotFoundError:
        return []


def export_log_csv(path, csv_path):
    records = read_log(path)
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question", "answer", "escalated", "sources"])
        writer.writeheader()
        for record in records:
            writer.writerow({**{key: record[key] for key in ("question", "answer", "escalated")},
                             "sources": json.dumps(record["sources"], ensure_ascii=False)})
    return len(records)
