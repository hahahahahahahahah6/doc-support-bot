import contextlib
import csv
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from doc_support_bot.answer import DONT_KNOW, answer_question
from doc_support_bot.cli import main
from doc_support_bot.evaluate import evaluate
from doc_support_bot.ingest import build_index, load_index
from doc_support_bot.retrieve import search, tokenize
from doc_support_bot.server import make_handler
from doc_support_bot.store import export_log_csv, log_qa, read_log


class BotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.docs = self.root / 'docs'
        self.docs.mkdir()
        (self.docs / 'shipping.md').write_text('# Shipping\n\nShipping is free over $50.\n\n## Timing\n\nDelivery takes 3-5 business days.\n')
        (self.docs / 'returns.txt').write_text('Returns accepted within 30 days.\n')
        self.index = build_index(self.docs)
        self.index_path = self.root / 'index.json'
        self.index_path.write_text(json.dumps(self.index))
        self.log = self.root / 'log.jsonl'

    def test_headings(self):
        self.assertEqual([c['section'] for c in self.index['chunks']], ['', 'Shipping', 'Timing'])

    def test_paragraph_split(self):
        self.assertEqual(len(self.index['chunks']), 3)

    def test_txt(self):
        self.assertEqual(self.index['chunks'][0]['text'], 'Returns accepted within 30 days.')

    def test_empty_dir(self):
        empty = self.root / 'empty'
        empty.mkdir()
        self.assertEqual(build_index(empty)['chunks'], [])

    def test_empty_file(self):
        (self.docs / 'empty.md').write_text(' \n')
        self.assertEqual(len(build_index(self.docs)['chunks']), 3)

    def test_ignore(self):
        (self.docs / 'secret.json').write_text('ignored')
        self.assertNotIn('secret.json', build_index(self.docs)['docs'])

    def test_sorted(self):
        self.assertEqual(self.index['docs'], ['returns.txt', 'shipping.md'])

    def test_recursive(self):
        (self.docs / 'nested').mkdir()
        (self.docs / 'nested' / 'a.md').write_text('Nested words')
        self.assertEqual(build_index(self.docs)['docs'][0], 'nested/a.md')

    def test_load(self):
        self.assertEqual(load_index(self.index_path), self.index)

    def test_exact_term(self):
        self.assertEqual(search(self.index, 'shipping')[0]['chunk']['doc'], 'shipping.md')

    def test_unknown_score(self):
        self.assertTrue(all(r['score'] == 0 for r in search(self.index, 'quantum physics')))

    def test_empty_query(self):
        self.assertTrue(all(r['score'] == 0 for r in search(self.index, '')))

    def test_bounds(self):
        self.assertTrue(all(0 <= r['score'] <= 1 for r in search(self.index, 'shipping days')))

    def test_tokenize(self):
        self.assertEqual(tokenize('PLEASE Shipping! x 50 THE'), ['shipping', '50'])

    def test_top_k(self):
        self.assertEqual(len(search(self.index, 'days', 1)), 1)

    def test_known_answer(self):
        result = answer_question(self.index, 'shipping')
        self.assertFalse(result['escalated'])
        self.assertEqual(result['sources'][0]['doc'], 'shipping.md')

    def test_unknown_answer(self):
        result = answer_question(self.index, 'quantum physics')
        self.assertTrue(result['escalated'])
        self.assertEqual(result['answer'], DONT_KNOW)
        self.assertEqual(result['sources'], [])

    def test_empty_question(self):
        self.assertEqual(answer_question(self.index, '  ')['answer'], 'Please ask a question.')

    def test_verbatim(self):
        result = answer_question(self.index, 'shipping')
        self.assertIn(result['answer'], [c['text'] for c in self.index['chunks']])
        self.assertEqual(result['answer'], result['sources'][0]['snippet'])

    def test_length_limit(self):
        index = {'chunks': [{'doc': 'long', 'section': '', 'text': 'shipping ' * 100}]}
        self.assertEqual(len(answer_question(index, 'shipping')['answer']), 600)

    def test_no_overlap_zero_threshold(self):
        self.assertTrue(answer_question(self.index, 'quantum', threshold=0)['escalated'])

    def record(self):
        return {'question': 'shipping', **answer_question(self.index, 'shipping')}

    def test_log_roundtrip(self):
        log_qa(self.log, self.record())
        log_qa(self.log, self.record())
        records = read_log(self.log)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['question'], 'shipping')
        self.assertTrue(records[0]['ts'].endswith('+00:00'))

    def test_missing_log(self):
        self.assertEqual(read_log(self.log), [])

    def test_csv(self):
        log_qa(self.log, self.record())
        target = self.root / 'export.csv'
        self.assertEqual(export_log_csv(self.log, target), 1)
        with target.open(newline='') as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows[0], ['question', 'answer', 'escalated', 'sources'])
        self.assertEqual(len(rows), 2)
        self.assertTrue(json.loads(rows[1][3]))

    def test_eval_rates(self):
        metrics = evaluate(self.index, [{'question': 'shipping', 'expected_doc': 'shipping.md'}])
        self.assertEqual(metrics['answered'], 1)
        for name in ('answer_rate', 'escalation_rate', 'citation_coverage', 'mean_top_score'):
            self.assertTrue(0 <= metrics[name] <= 1)

    def test_eval_unknown(self):
        self.assertEqual(evaluate(self.index, [{'question': 'quantum', 'expected_doc': None}])['escalated'], 1)

    def test_eval_empty(self):
        self.assertEqual(evaluate(self.index, [])['total'], 0)

    def cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(args)
        return output.getvalue()

    def test_cli_ingest(self):
        self.assertIn('3 chunks', self.cli(['ingest', str(self.docs), '--index', str(self.index_path)]))

    def test_cli_ask(self):
        self.assertFalse(json.loads(self.cli(['ask', '--index', str(self.index_path), '--question', 'shipping']))['escalated'])

    def test_cli_export(self):
        log_qa(self.log, self.record())
        self.assertIn('1 rows', self.cli(['export-log', '--log', str(self.log), '--csv', str(self.root / 'out.csv')]))

    def test_cli_eval(self):
        qa = self.root / 'qa.json'
        qa.write_text('[{"question":"shipping","expected_doc":"shipping.md"}]')
        self.assertEqual(json.loads(self.cli(['eval', '--index', str(self.index_path), '--qa', str(qa)]))['answered'], 1)

    def test_version(self):
        result = subprocess.run([sys.executable, '-m', 'doc_support_bot', '--version'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), '0.1.0')

    def test_missing_subcommand(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / 'qa.jsonl'
        index = {'chunks': [{'doc': 'shipping.md', 'section': 'Shipping', 'text': 'Shipping is free over $50.'}]}
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(index, self.log))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None):
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            return response.status, response.read().decode()
        finally:
            connection.close()

    def test_health(self):
        status, data = self.request('GET', '/health')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data), {'status': 'ok'})

    def test_known(self):
        status, data = self.request('POST', '/ask', '{"question":"shipping"}')
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(data)['escalated'])
        self.assertEqual(len(read_log(self.log)), 1)

    def test_unknown(self):
        status, data = self.request('POST', '/ask', '{"question":"quantum"}')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)['answer'], DONT_KNOW)

    def test_not_found(self):
        self.assertEqual(self.request('GET', '/missing')[0], 404)
        self.assertEqual(self.request('POST', '/missing')[0], 404)

    def test_bad_json(self):
        for body in ('broken', '{}', '[]', '{"question":4}'):
            self.assertEqual(self.request('POST', '/ask', body)[0], 400)

    def test_pages(self):
        self.assertIn('/widget', self.request('GET', '/')[1])
        self.assertIn('fetch', self.request('GET', '/widget')[1])

    def test_logs(self):
        self.assertEqual(json.loads(self.request('GET', '/logs')[1]), {'logs': []})
        self.request('POST', '/ask', '{"question":"shipping"}')
        self.assertEqual(len(json.loads(self.request('GET', '/logs')[1])['logs']), 1)


if __name__ == '__main__':
    unittest.main()
