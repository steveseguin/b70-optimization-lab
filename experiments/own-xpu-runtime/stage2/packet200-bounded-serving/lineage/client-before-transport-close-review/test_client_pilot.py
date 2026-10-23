"""CPU-only fixed-client checks; every HTTP call is intercepted."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('p200_client_tests', P / 'client_pilot.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


class ExerciseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors, cls.codec = C.plan()  # Actual pinned codec and vector rendering, no request.

    def setUp(self):
        self.calls = []; self.saved = {}; self.native = {}; self.seen = {}; self.turn = 0
        self.change = lambda request, response, native, inputs: None
        self.invalid_status = 400

    def transport(self, address, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == '/health': return dict(status=200, body={'status':'ready'})
        if path == '/v1/models': return dict(status=200, body={'data':[{'id':C.MODEL}]})
        if kwargs['payload']['temperature'] != 0: return dict(status=self.invalid_status, body={'error':{}})
        row = self.vectors['rows'][self.turn]; self.turn += 1
        self.assertEqual(kwargs['payload'], row['body']); self.assertEqual(kwargs['session'], row['session'])
        tokens = list(row.get('expected_tokens', [1000 + self.turn] * row['body']['max_tokens']))
        if 'compare_tokens_to' in row: tokens = list(self.seen[row['compare_tokens_to']])
        self.seen[row['name']] = tokens
        request_id = 'h' + 'a' * 32 + '-' + format(self.turn + 1, '016x')
        native = dict(passed=True, request_front_scope='experimental-postreply-owner-v2', context=4096,
            requested_max_new=row['body']['max_tokens'], prompt_tokens=len(row['prompt_tokens']),
            session_reuse=row.get('expected_reuse', False), tokens=tokens)
        body = dict(id='chatcmpl-' + request_id, object='chat.completion', model=C.MODEL,
            choices=[dict(index=0, message=dict(role='assistant', content=self.codec.decode(tokens)), finish_reason='length')],
            usage=dict(prompt_tokens=len(row['prompt_tokens']), completion_tokens=len(tokens), total_tokens=len(row['prompt_tokens'])+len(tokens)))
        response = dict(status=200, body=body, raw_sha256='synthetic-transport')
        inputs = list(row['prompt_tokens'])
        self.change(row, response, native, inputs)
        self.native[request_id] = (native, C.digest(C.encoded(native)), inputs, C.digest(C.encoded(inputs)))
        return response

    def exercise(self, guard=lambda: None):
        return C.exercise(('127.0.0.1',1234), self.vectors, self.codec,
            native_reader=lambda request_id:self.native[request_id], guard=guard,
            persist=lambda name,row:self.saved.__setitem__(name,copy.deepcopy(row)), transport=self.transport)

    def test_actual_plan_and_full_flow(self):
        result = self.exercise()
        self.assertTrue(result['passed']); self.assertEqual(len(self.calls),19)
        self.assertEqual(result['requests'],16); self.assertEqual(result['output_tokens'],1728)
        self.assertEqual(result['exact_recorded_requests'],5); self.assertEqual(result['resumed_fresh_pairs'],1)
        self.assertFalse(result['speed_claim']); self.assertFalse(result['submission_eligible'])
        self.assertEqual(len([name for name in self.saved if name.endswith('-native.json')]),16)

    def test_invalid_sampling_acceptance_stops_before_valid_requests(self):
        self.invalid_status=200
        with self.assertRaisesRegex(RuntimeError,'not refused'): self.exercise()
        self.assertEqual(len(self.calls),3); self.assertEqual(self.turn,0)

    def test_unexpected_http_response_retained_without_retry(self):
        def change(row,response,native,inputs):
            if row['name']=='a-chat-append': response['status']=503
        self.change=change
        with self.assertRaisesRegex(RuntimeError,'unexpected HTTP status'): self.exercise()
        self.assertEqual(len(self.calls),6); self.assertEqual(self.turn,3)
        self.assertEqual(self.saved['03-http.json']['response']['status'],503)
        self.assertNotIn('03-native.json',self.saved)

    def test_wrong_oracle_after_matching_http_decode_stops(self):
        def change(row,response,native,inputs):
            native['tokens'][0]=1000
            response['body']['choices'][0]['message']['content']=self.codec.decode(native['tokens'])
        self.change=change
        with self.assertRaisesRegex(RuntimeError,'oracle mismatch'): self.exercise()
        self.assertEqual(len(self.calls),4)

    def test_resumed_fresh_pair_mismatch_stops(self):
        def change(row,response,native,inputs):
            if row['name']=='a-chat-fresh':
                native['tokens'][0]=1000
                response['body']['choices'][0]['message']['content']=self.codec.decode(native['tokens'])
        self.change=change
        with self.assertRaisesRegex(RuntimeError,'resumed/fresh'): self.exercise()
        self.assertEqual(self.turn,4)

    def test_same_length_wrong_consumed_prompt_stops(self):
        def change(row,response,native,inputs):
            if row['name']=='names': inputs[0]=1000
        self.change=change
        with self.assertRaisesRegex(RuntimeError,'consumed prompt'): self.exercise()
        self.assertEqual(self.turn,7)

    def test_wrong_usage_and_request_path_refuse(self):
        self.change=lambda r,s,n,i:s['body']['usage'].update(total_tokens=0)
        with self.assertRaisesRegex(RuntimeError,'usage'): self.exercise()
        self.assertEqual(self.turn,1)

    def test_request_id_cannot_escape_native_root(self):
        self.change=lambda r,s,n,i:s['body'].update(id='chatcmpl-../../elsewhere')
        with self.assertRaisesRegex(RuntimeError,'request identity'): self.exercise()
        self.assertEqual(self.turn,1)

    def test_guard_refusal_prevents_any_http(self):
        error=RuntimeError('halted')
        with self.assertRaises(RuntimeError) as caught:
            self.exercise(guard=lambda:(_ for _ in ()).throw(error))
        self.assertIs(caught.exception,error); self.assertEqual(self.calls,[])

    def test_natural_stop_mapping_for_unoracled_prompt(self):
        def change(row,response,native,inputs):
            if row['name']=='names':
                native['tokens']=[1000,248046]
                response['body']['choices'][0].update(message=dict(role='assistant',content=self.codec.decode([1000])),finish_reason='stop')
                response['body']['usage'].update(completion_tokens=2,total_tokens=len(inputs)+2)
        self.change=change
        result=self.exercise();self.assertTrue(result['passed']);self.assertEqual(result['output_tokens'],1666)


class IOTests(unittest.TestCase):
    def test_transport_failure_has_one_attempt_and_closes(self):
        connection=Mock(); error=OSError('socket failed');connection.request.side_effect=error
        with patch.object(C.http.client,'HTTPConnection',return_value=connection) as constructor:
            with self.assertRaises(OSError) as caught:C.exchange(('127.0.0.1',1234),'GET','/health')
        self.assertIs(caught.exception,error);self.assertEqual(constructor.call_count,1)
        connection.request.assert_called_once();connection.close.assert_called_once()

    def test_response_bound_and_nonloopback_refuse(self):
        connection=Mock();connection.getresponse.return_value.read.return_value=b'x'*65537
        with patch.object(C.http.client,'HTTPConnection',return_value=connection):
            with self.assertRaisesRegex(RuntimeError,'bound'):C.exchange(('127.0.0.1',1234),'GET','/health')
        connection.close.assert_called_once()
        with patch.object(C.http.client,'HTTPConnection',side_effect=AssertionError('no network')):
            with self.assertRaisesRegex(RuntimeError,'loopback'):C.exchange(('localhost',1234),'GET','/health')

    def test_native_read_is_bounded_regular_and_not_a_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input';path.write_bytes(b'1\n2\n')
            self.assertEqual(C.bounded_read(path,4),b'1\n2\n')
            with self.assertRaises(RuntimeError):C.bounded_read(path,3)
            link=Path(tmp)/'link';link.symlink_to(path)
            with self.assertRaises(RuntimeError):C.bounded_read(link,10)
            fifo=Path(tmp)/'fifo';os.mkfifo(fifo)
            with self.assertRaises(RuntimeError):C.bounded_read(fifo,10)


class ExecuteTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.stage=self.root/'stage';(self.stage/'output/control').mkdir(parents=True)
        (self.stage/'output/control/events.jsonl').write_bytes(C.encoded(dict(event='listener',address=['127.0.0.1',1234])))
        self.output=self.root/'client';self.stop=self.stage/'output/STOP'
        self.manifest=self.root/'manifest';self.manifest.write_bytes(b'admitted fixture')
        admission=SimpleNamespace(MANIFEST=self.manifest,verify_manifest=lambda:({'controller':{'additional_write_bytes':C.LIMIT}},C.digest(self.manifest.read_bytes())))
        loader=SimpleNamespace(exec_module=lambda module:None)
        mocks=[patch.object(C,'STAGE',self.stage),patch.object(C,'OUTPUT',self.output),
            patch.object(C.importlib.util,'spec_from_file_location',return_value=SimpleNamespace(loader=loader)),
            patch.object(C.importlib.util,'module_from_spec',return_value=admission),
            patch.object(C,'plan',return_value=({},None))]
        for mock in mocks:mock.start();self.addCleanup(mock.stop)

    def test_postadmission_initialization_failure_sets_stop(self):
        error=RuntimeError('codec refused')
        with patch.object(C,'plan',side_effect=error),patch.object(C,'exchange',side_effect=AssertionError('no HTTP')):
            with self.assertRaises(RuntimeError) as caught:C.execute()
        self.assertIs(caught.exception,error);self.assertTrue(self.stop.exists());self.assertFalse(self.output.exists())

    def test_primary_error_survives_stop_and_close_failures(self):
        original=RuntimeError('native oracle failed');actual_open=Path.open;actual_close=C.BoundedEvidence.close
        def opening(path,*args,**kwargs):
            if path==self.stop:raise OSError('STOP failed')
            return actual_open(path,*args,**kwargs)
        def closing(writer):actual_close(writer);raise OSError('close failed')
        with (patch.object(C,'exercise',side_effect=original),patch.object(Path,'open',opening),
              patch.object(C.BoundedEvidence,'close',closing)):
            with self.assertRaises(RuntimeError) as caught:C.execute()
        self.assertIs(caught.exception,original)
        self.assertIn('STOP failed',' '.join(original.__notes__));self.assertIn('close failed',' '.join(original.__notes__))
        self.assertFalse(json.loads((self.output/'client-incident.json').read_text())['passed'])

    def test_close_failure_after_provisional_pass_is_failure_and_stop(self):
        original=OSError('final close failed');actual_close=C.BoundedEvidence.close
        def closing(writer):actual_close(writer);raise original
        with patch.object(C,'exercise',return_value={'passed':True}),patch.object(C.BoundedEvidence,'close',closing):
            with self.assertRaises(OSError) as caught:C.execute()
        self.assertIs(caught.exception,original);self.assertTrue(self.stop.exists())
        self.assertTrue(json.loads((self.output/'client-result.json').read_text())['passed'])
        # Therefore controller must also require successful client-unit exit.


if __name__=='__main__':unittest.main()
