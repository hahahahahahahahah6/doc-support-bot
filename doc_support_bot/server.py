"""Single-merchant standard-library HTTP service."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .answer import answer_question
from .ingest import build_index, load_index
from .store import log_qa, read_log

WIDGET = """<!doctype html><html lang="en"><meta charset="utf-8"><title>Support</title>
<form id="ask"><label>Question <input name="question" required></label><button>Ask</button></form>
<pre id="result"></pre><script>
document.getElementById('ask').onsubmit = async event => {
 event.preventDefault();
 const response = await fetch('/ask', {method:'POST', headers:{'Content-Type':'application/json'},
 body:JSON.stringify({question:event.target.question.value})});
 document.getElementById('result').textContent = JSON.stringify(await response.json(), null, 2);
};</script></html>"""


def make_handler(index, log_path=None):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, payload, html=False):
            data = (payload if html else json.dumps(payload)).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self.send(200, {"status": "ok"})
            elif self.path == "/logs":
                self.send(200, {"logs": read_log(log_path)})
            elif self.path == "/widget":
                self.send(200, WIDGET, html=True)
            elif self.path == "/":
                self.send(200, '<!doctype html><html lang="en"><title>Document support</title><h1>Document support</h1><p>POST a JSON question to /ask. GET /health or /logs.</p><a href="/widget">Ask support</a></html>', html=True)
            else:
                self.send(404, {"error": "Not found"})

        def do_POST(self):
            if self.path != "/ask":
                self.send(404, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 1048576:
                    raise ValueError("Invalid body size")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or not isinstance(payload.get("question"), str):
                    raise ValueError("question must be a string")
            except (ValueError, UnicodeError):
                self.send(400, {"error": "Expected JSON with a string question"})
                return
            result = {"question": payload["question"], **answer_question(index, payload["question"])}
            if log_path:
                log_qa(log_path, result)
            self.send(200, result)

        def log_message(self, format, *args):
            pass
    return Handler


def serve(index, host="127.0.0.1", port=8000, log_path=None):
    with ThreadingHTTPServer((host, port), make_handler(index, log_path)) as server:
        server.serve_forever()


def run_server(docs_dir=None, index_path=None, host="127.0.0.1", port=8000, log_path=None):
    if (docs_dir is None) == (index_path is None):
        raise ValueError("Supply exactly one of docs_dir or index_path")
    serve(build_index(docs_dir) if docs_dir is not None else load_index(index_path), host, port, log_path)


def main(argv=None):
    from .cli import main as cli_main
    return cli_main(["serve"] + (argv if argv is not None else __import__("sys").argv[1:]))
