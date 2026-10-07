import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest

spec = importlib.util.spec_from_file_location('entry', Path(__file__).with_name('run_guarded_worker.py'))
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)


class GuardTests(unittest.TestCase):
    def fixture(self, root, response):
        calls = []
        def request(*args, **kwargs):
            calls.append('generation'); return response
        def write(path, value):
            path.write_text(json.dumps(value))
        model = types.SimpleNamespace(max_input=28000,
            opener=types.SimpleNamespace(open=lambda *a, **k: calls.append('open')),
            wire=types.SimpleNamespace(request_one=request, write_json=write),
            query=lambda *a, **k: calls.append('query'))
        (root / 'token-count.json').write_text(json.dumps({'input_tokens': 400}))
        return model, calls

    def response(self):
        return {'finish_reasons':['stop'], 'cached_tokens':0, 'prompt_tokens':400,
                'token_ids_available':True, 'token_ids':[1], 'completion_tokens':1}

    def test_fault_blocks_query_network_and_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'STOP').write_text('stop')
            model, calls = self.fixture(root, self.response())
            E.guard_model(model, E.make_health_guard(root))
            for call in [lambda:model.query([]), lambda:model.opener.open('unused'),
                         lambda:model.wire.request_one('', {'max_tokens':512}, root)]:
                with self.assertRaises(RuntimeError): call()
            self.assertEqual(calls, [])

    def test_cached_response_refused_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); response=self.response(); response['cached_tokens']=1
            model,calls=self.fixture(root,response); E.guard_model(model,lambda:None)
            with self.assertRaisesRegex(ValueError,'zero cached'):
                model.wire.request_one('',{'max_tokens':512},root)
            self.assertEqual(calls,['generation'])
            self.assertEqual(json.loads((root/'guard-response.json').read_text()),response)

    def test_truncation_refused_and_valid_complete_response_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); response=self.response(); response['finish_reasons']=['length']
            model,calls=self.fixture(root,response); E.guard_model(model,lambda:None)
            with self.assertRaisesRegex(ValueError,'Natural stop'):
                model.wire.request_one('',{'max_tokens':512},root)
            self.assertEqual(calls,['generation'])
            response['finish_reasons']=['stop']
            # Separate valid fixture/control, not a retry of a real request.
            model,calls=self.fixture(root,response); E.guard_model(model,lambda:None)
            self.assertEqual(model.wire.request_one('',{'max_tokens':512},root),response)
            self.assertEqual(calls,['generation'])


if __name__=='__main__': unittest.main()
