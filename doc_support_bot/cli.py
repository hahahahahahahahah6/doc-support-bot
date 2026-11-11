"""Command-line interface."""
import argparse
import json
from . import __version__
from .answer import answer_question
from .evaluate import evaluate
from .ingest import build_index, load_index
from .server import run_server
from .store import export_log_csv


def main(argv=None):
    parser = argparse.ArgumentParser(prog="doc-support-bot")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("docs_dir")
    ingest.add_argument("--index", required=True)
    ask = commands.add_parser("ask")
    ask.add_argument("--index", required=True)
    ask.add_argument("--question", required=True)
    server = commands.add_parser("serve")
    source = server.add_mutually_exclusive_group(required=True)
    source.add_argument("--docs")
    source.add_argument("--index")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8000)
    server.add_argument("--log")
    export = commands.add_parser("export-log")
    export.add_argument("--log", required=True)
    export.add_argument("--csv", required=True)
    evaluation = commands.add_parser("eval")
    evaluation.add_argument("--index", required=True)
    evaluation.add_argument("--qa", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest":
            index = build_index(args.docs_dir)
            with open(args.index, "w", encoding="utf-8") as handle:
                json.dump(index, handle, ensure_ascii=False, indent=2)
            print(str(len(index["chunks"])) + " chunks")
        elif args.command == "ask":
            print(json.dumps(answer_question(load_index(args.index), args.question), ensure_ascii=False))
        elif args.command == "serve":
            run_server(args.docs, args.index, args.host, args.port, args.log)
        elif args.command == "export-log":
            print(str(export_log_csv(args.log, args.csv)) + " rows")
        elif args.command == "eval":
            with open(args.qa, encoding="utf-8") as handle:
                pairs = json.load(handle)
            print(json.dumps(evaluate(load_index(args.index), pairs)))
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    return 0
