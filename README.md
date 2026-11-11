# doc-support-bot

A standard-library-only support bot for a single merchant's Markdown and text
documents. TF-IDF retrieves verbatim snippets with citations. Its don't-know
response flags questions for human follow-up and can be recorded in local logs.
Version 0.1.0; Python 3.9 or newer. No runtime dependencies or external services.

## Run

From the project directory:

```sh
python3 -m doc_support_bot --version
python3 -m doc_support_bot ingest examples/docs --index /tmp/support-index.json
python3 -m doc_support_bot ask --index /tmp/support-index.json --question "How long does shipping take?"
python3 -m doc_support_bot ask --index /tmp/support-index.json --question "Explain quantum physics"
python3 -m doc_support_bot eval --index /tmp/support-index.json --qa examples/qa.json
python3 -m doc_support_bot serve --docs examples/docs --host 127.0.0.1 --port 8000 --log /tmp/support-log.jsonl
```

Alternatively serve with `--index /tmp/support-index.json` instead of `--docs`.
Open http://127.0.0.1:8000/widget to ask questions. Stop with Ctrl-C.
CLI `ask` prints an answer without logging; HTTP `/ask` logs when `--log` is set.
Export after asking through the server:

```sh
python3 -m doc_support_bot export-log --log /tmp/support-log.jsonl --csv /tmp/support-log.csv
python3 -m unittest discover -s tests -v
python3 -m pip install .
doc-support-bot --version
```

Build with `python3 -m build` when installed, or
`python3 -m pip wheel . --no-deps --wheel-dir dist` for a wheel.

## Retrieval and index

Documents are loaded recursively in sorted path order. Markdown headings set
section names; blank lines separate paragraphs. Empty content and other file
types are skipped. JSON indexes contain `chunks` (doc, section, text), `docs`,
and the equivalent `built_from` list, retaining both names used by the spec.
Document paths are relative to the docs directory.

Tokens are lowercase ASCII letters/digits, at least two characters, with a small
stopword list. Raw term counts are weighted by `log((N+1)/(df+1))+1`, then ranked
by cosine similarity. Query terms absent from the corpus still contribute to
the query norm. Ties retain document/paragraph order. Default threshold: 0.08.
Answers copy at most 600 characters from the top chunk, with up to three cited
snippets scoring at least half the threshold. No overlap or a low top score
returns exactly: "I don't know based on the provided documents. A human will follow up."
An empty question returns "Please ask a question." Both cases escalate.
Escalation is a response flag and log entry; no human notification is sent.

## HTTP API

- `GET /health`: `{"status":"ok"}`.
- `POST /ask`: JSON `{"question":"How long does shipping take?"}`.
  Returns `question`, `answer`, `escalated`, and `sources`. Each citation has
  `doc`, `section`, `score` (rounded to three decimals), and `snippet`.
- `GET /logs`: `{"logs":[...]}`, empty without a configured log file.
- `GET /widget`: HTML form using fetch; `GET /`: usage and widget link.
- Unknown routes: JSON 404. Invalid JSON or missing/non-string question: JSON 400.

Logs append UTC ISO timestamps and Q&A records as UTF-8 JSONL. CSV columns are
`question,answer,escalated,sources`; sources are JSON within a CSV cell.
Logs are accessible to anyone who can reach the server. Use trusted local access.

## Evaluation

`eval` reads `{question, expected_doc}` fixtures and computes total, answered,
escalated, answer_rate, escalation_rate, citation_coverage (answered responses
with sources / answered responses), and mean_top_score (including unknowns).
Empty denominators produce zero. `expected_doc` is fixture metadata; these
metrics do not compare it against retrieved citations and are not accuracy
measurements. Run evaluation on your own documents and questions.

## Pricing suggestion

Suggestion only, with no revenue or service promise: Starter $9/mo (1 docs set,
500 questions/mo), Pro $29/mo (5 docs sets, unlimited questions, log export).
Self-host free. These are possible hosted offerings; this MVP does not implement
plan limits or multiple docs sets per server.

## Honest limitations

- Keyword TF-IDF only: no semantic understanding; synonyms and paraphrases may
  miss. No multilingual support beyond tokenisation.
- Answers are verbatim snippets from merchant docs, not generated prose. If docs
  are wrong or stale, answers repeat them. Lexical overlap can select irrelevant
  content; the threshold is a heuristic, not a correctness guarantee.
- No auth, no multi-tenancy, no payments built in: single merchant, single docs
  set per server. Pricing is a suggestion only.
- No uptime/SLA. The log is local JSONL, not a database. Append locking is within
  one process only; malformed log lines raise errors rather than being repaired.
- Retrieval recomputes vectors for each question; the MVP suits small document
  sets. The widget displays JSON and has no production chat UX or ticket system.

MIT licensed; see LICENSE.
