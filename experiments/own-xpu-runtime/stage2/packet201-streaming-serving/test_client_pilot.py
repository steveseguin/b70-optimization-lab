"""CPU-only fixed-client checks; every HTTP call is intercepted."""
import copy
import importlib.util
import json
import io
import base64
import socket
import threading
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('p201_client_tests', P / 'client_pilot.py')
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
        tokens = list(row['p200_baseline']['tokens'])
        if 'compare_tokens_to' in row: tokens = list(self.seen[row['compare_tokens_to']])
        self.seen[row['name']] = tokens
        request_id = 'h' + 'a' * 32 + '-' + format(self.turn + 1, '016x')
        native = dict(passed=True, request_front_scope='experimental-postreply-owner-v2', context=4096,
            requested_max_new=row['body']['max_tokens'], prompt_tokens=len(row['prompt_tokens']),
            session_reuse=row.get('expected_reuse', False), tokens=tokens)
        body = dict(id='chatcmpl-' + request_id, object='chat.completion', model=C.MODEL,
            choices=[dict(index=0, message=dict(role='assistant', content=row['p200_baseline']['text']), finish_reason=row['p200_baseline']['finish_reason'])],
            usage=dict(prompt_tokens=len(row['prompt_tokens']), completion_tokens=len(tokens), total_tokens=len(row['prompt_tokens'])+len(tokens)))
        response = dict(status=200, body=body, raw_sha256='synthetic-transport',sse_validated=bool(row['body']['stream']),done=bool(row['body']['stream']))
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
        self.assertEqual(result['requests'],16); self.assertEqual(result['output_tokens'],1484)
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

    def test_changed_natural_stop_refuses_exact_p200_baseline(self):
        def change(row,response,native,inputs):
            if row['name']=='names':
                native['tokens']=[1000,248046]
                response['body']['choices'][0].update(message=dict(role='assistant',content=self.codec.decode([1000])),finish_reason='stop')
                response['body']['usage'].update(completion_tokens=2,total_tokens=len(inputs)+2)
        self.change=change
        with self.assertRaisesRegex(RuntimeError,'p200 full native baseline'):self.exercise()
        self.assertEqual(self.turn,7)


class IOTests(unittest.TestCase):
    def test_transport_error_survives_connection_close_error(self):
        connection=Mock();error=OSError('original request failure')
        connection.request.side_effect=error;connection.close.side_effect=OSError('secondary close failure')
        with patch.object(C.http.client,'HTTPConnection',return_value=connection):
            with self.assertRaises(OSError) as caught:C.exchange(('127.0.0.1',1234),'GET','/health')
        self.assertIs(caught.exception,error);self.assertIn('secondary close failure',' '.join(error.__notes__))
        connection.request.assert_called_once();connection.close.assert_called_once()

    def test_transport_failure_has_one_attempt_and_closes(self):
        connection=Mock(); error=OSError('socket failed');connection.request.side_effect=error
        with patch.object(C.http.client,'HTTPConnection',return_value=connection) as constructor:
            with self.assertRaises(OSError) as caught:C.exchange(('127.0.0.1',1234),'GET','/health')
        self.assertIs(caught.exception,error);self.assertEqual(constructor.call_count,1)
        connection.request.assert_called_once();connection.close.assert_called_once()

    def test_response_and_connection_close_keep_original_parse_error(self):
        connection=Mock();reply=connection.getresponse.return_value
        original=OSError('original response parse failure');reply.read.side_effect=original
        reply.close.side_effect=OSError('response close secondary')
        connection.close.side_effect=OSError('connection close secondary')
        with patch.object(C.http.client,'HTTPConnection',return_value=connection):
            with self.assertRaises(OSError) as caught:C.exchange(('127.0.0.1',1234),'GET','/health')
        self.assertIs(caught.exception,original)
        reply.close.assert_called_once();connection.close.assert_called_once()
        self.assertIn('response close secondary',' '.join(original.__notes__))
        self.assertIn('connection close secondary',' '.join(original.__notes__))

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


class SSETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors,cls.codec=C.plan()

    def wire(self,row,*,tokens=None,request_id=None):
        from streaming_v1.decoder import TokenDecoder
        from streaming_v1.delivery import sse_event
        tokens=row['p200_baseline']['tokens'] if tokens is None else tokens
        identity=dict(id=request_id or 'chatcmpl-h'+'a'*32+'-'+format(2,'016x'),
                      object='chat.completion.chunk',created=1790000000,model=C.MODEL)
        def chunk(delta,finish=None,usage=None):
            result=identity|dict(choices=[dict(index=0,delta=delta,finish_reason=finish)])
            if usage is not None:result['usage']=usage
            return sse_event(result)
        parts=[chunk({'role':'assistant','content':''})]
        decoder=TokenDecoder(self.codec,maximum_tokens=row['body']['max_tokens'])
        for token in tokens:
            text=decoder.feed(token)
            if text:parts.append(chunk({'content':text}))
        tail=decoder.finish(tokens)
        if tail:parts.append(chunk({'content':tail}))
        terminal=tokens[-1] in self.codec.terminal_token_ids
        usage=dict(prompt_tokens=len(row['prompt_tokens']),completion_tokens=len(tokens),
                   total_tokens=len(row['prompt_tokens'])+len(tokens))
        parts.extend([chunk({},'stop' if terminal else 'length',usage),b'data: [DONE]\n\n'])
        return b''.join(parts)

    def parse(self,raw,maximum=256):
        class Reply(io.BytesIO):
            status=200
            def getheader(self,key):return 'text/event-stream; charset=utf-8'
            def read(self,*args):raise AssertionError('SSE must not wait for whole response')
        return C.read_sse(Reply(raw),maximum=maximum,receive_socket=Mock())

    def test_strict_sse_replay_full_flow_and_encoded_evidence_budget(self):
        fixture=ExerciseTests('test_actual_plan_and_full_flow');fixture.vectors=self.vectors;fixture.codec=self.codec;fixture.setUp()
        ordinary=fixture.transport
        def transport(address,method,path,**kwargs):
            response=ordinary(address,method,path,**kwargs)
            if response['status']==200 and kwargs.get('payload',{}).get('stream'):
                row=self.vectors['rows'][fixture.turn-1]
                return self.parse(self.wire(row,request_id=response['body']['id']),row['body']['max_tokens'])
            return response
        result=C.exercise(('127.0.0.1',1234),self.vectors,self.codec,
            native_reader=lambda rid:fixture.native[rid],guard=lambda:None,
            persist=lambda name,row:fixture.saved.__setitem__(name,copy.deepcopy(row)),transport=transport)
        self.assertEqual(result['p200_exact_requests'],16);self.assertEqual(result['sse_requests'],7)
        self.assertEqual(result['ordinary_requests'],9);self.assertEqual(result['sse_terminal_sequences'],7)
        self.assertEqual(result['output_tokens'],1484)
        rows=list(fixture.saved.values())+[result,{'admission':'0'*2048}]
        sizes=[len(C.encoded(row)) for row in rows]
        self.assertEqual(len(rows),37);self.assertLess(max(sizes),C.RECORD_LIMIT);self.assertLess(sum(sizes),C.LIMIT)
        self.actual_budget_bytes=sum(sizes)
        # Conservative cap replay uses the largest escaped display token among
        # actual baseline pieces. This is an estimate, not a universal log bound;
        # production BoundedEvidence still refuses any total beyond1MiB.
        candidates={t for row in self.vectors['rows'] for t in row['p200_baseline']['tokens']
                    if t not in self.codec.terminal_token_ids}
        token=max(candidates,key=lambda t:len(C.encoded(self.codec.decode([t]))))
        capped=[]
        for row in self.vectors['rows']:
            tokens=[token]*row['body']['max_tokens'];usage=dict(prompt_tokens=len(row['prompt_tokens']),
                completion_tokens=len(tokens),total_tokens=len(row['prompt_tokens'])+len(tokens))
            response=(self.parse(self.wire(row,tokens=tokens),len(tokens)) if row['body']['stream'] else
                dict(status=200,body={'choices':[{'message':{'content':self.codec.decode(tokens)}}],'usage':usage}))
            capped.append({'name':row['name'],'response':response})
            capped.append(dict(name=row['name'],tokens=tokens,native_input_tokens=row['prompt_tokens'],
                native_result_sha256='a'*64,native_input_sha256='b'*64))
        capped.extend([{'reserved_metadata':'x'*4096}]*5)
        cap_sizes=[len(C.encoded(row)) for row in capped]
        self.assertLess(max(cap_sizes),C.RECORD_LIMIT);self.assertLess(sum(cap_sizes),C.LIMIT)
        print('ENCODED_BUDGET '+json.dumps(dict(baseline_tokens=1484,baseline_bytes=sum(sizes),
            cap_tokens=1728,cap_replay_estimate_bytes=sum(cap_sizes),files=37,limit_bytes=C.LIMIT,
            cap_replay_is_universal_bound=False)))

    def test_malformed_utf8_keys_identity_and_terminal_sequences_refuse(self):
        raw=self.wire(self.vectors['rows'][0]);parts=raw.split(b'\n\n')
        cases={
            'utf8':raw.replace(b'"assistant"',b'"\xff"',1),
            'duplicate-key':raw.replace(b'"model":',b'"model":"x","model":',1),
            'changed-id':b'\n\n'.join(parts[:1]+[parts[1].replace(b'chatcmpl-h',b'chatcmpl-hb',1)]+parts[2:]),
            'changed-created':b'\n\n'.join(parts[:1]+[parts[1].replace(b'1790000000',b'1790000001',1)]+parts[2:]),
            'missing-done':raw.removesuffix(b'data: [DONE]\n\n'),
            'missing-terminal':b'\n\n'.join(parts[:-3]+parts[-2:]),
            'done-first':b'data: [DONE]\n\n',
            'trailing':raw+b'x',
            'double-done':raw+b'data: [DONE]\n\n',
            'missing-delimiter':raw.replace(b'\n\n',b'\n',1),
            'oversized-line':b'data: '+b'x'*8193+b'\n\n',
            'surrogate':raw.replace(b'"assistant"',b'"\\ud800"',1),
        }
        for name,value in cases.items():
            with self.subTest(name=name),self.assertRaises((RuntimeError,UnicodeError,ValueError)) as caught:
                self.parse(value)
            partial=caught.exception.client_partial_response
            self.assertFalse(partial['sse_validated']);self.assertFalse(partial['done'])
            self.assertTrue(base64.b64decode(partial['raw_sse_base64']))
        with self.assertRaisesRegex(RuntimeError,'frame count'):self.parse(raw,1)
        with patch.object(C,'SSE_LIMIT',100):
            with self.assertRaisesRegex(RuntimeError,'bound') as caught:self.parse(raw)
            self.assertEqual(len(base64.b64decode(caught.exception.client_partial_response['raw_sse_base64'])),100)

    def test_detached_response_socket_enforces_remaining_deadline(self):
        raw=self.wire(self.vectors['rows'][0]);connection=Mock();receive=Mock()
        class Reply(io.BytesIO):
            status=200
            def getheader(self,key):return 'text/event-stream; charset=utf-8'
        connection.sock=receive
        def response():connection.sock=None;return Reply(raw)
        connection.getresponse.side_effect=response
        with patch.object(C.http.client,'HTTPConnection',return_value=connection):
            result=C.exchange(('127.0.0.1',1234),'POST','/v1/chat/completions',
                payload=self.vectors['rows'][0]['body'],session='test')
        self.assertTrue(result['done']);self.assertGreater(receive.settimeout.call_count,2)
        self.assertTrue(all(0<args.args[0]<=900 for args in receive.settimeout.call_args_list))
        with patch.object(C.time,'monotonic',side_effect=[0,901]):
            with self.assertRaisesRegex(RuntimeError,'deadline'):self.parse(raw)

    def test_real_http10_split_frame_is_consumed_before_eof(self):
        raw=self.wire(self.vectors['rows'][13]);first,rest=raw.split(b'\n\n',1)
        observed=threading.Event();errors=[]
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(2)
        def serve():
            try:
                with listener.accept()[0] as peer:
                    peer.settimeout(2);data=b''
                    while b'\r\n\r\n' not in data:data+=peer.recv(4096)
                    peer.sendall(b'HTTP/1.0 200 OK\r\nContent-Type: text/event-stream; charset=utf-8\r\nConnection: close\r\n\r\n')
                    peer.sendall(first[:17]);peer.sendall(first[17:]+b'\n\n')
                    if not observed.wait(2):raise RuntimeError('parser waited for EOF before first frame')
                    for offset in range(0,len(rest),13):peer.sendall(rest[offset:offset+13])
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=serve);thread.start();connection=C.http.client.HTTPConnection(*listener.getsockname(),timeout=2)
        try:
            connection.request('GET','/fixture');receive=connection.sock;reply=connection.getresponse()
            self.assertIsNone(connection.sock)
            class Observed:
                status=reply.status
                getheader=reply.getheader
                prefix=b''
                def read1(self,limit):
                    chunk=reply.read1(limit);self.prefix+=chunk
                    if b'\n\n' in self.prefix:observed.set()
                    return chunk
            result=C.read_sse(Observed(),maximum=32,receive_socket=receive)
            self.assertTrue(result['done']);self.assertGreater(len(result['received_frames']),2)
            self.assertEqual(result['body']['choices'][0]['message']['content'],self.vectors['rows'][13]['p200_baseline']['text'])
        finally:
            observed.set();connection.close();listener.close();thread.join(3)
        self.assertFalse(thread.is_alive());self.assertFalse(errors,errors)

    def test_trickled_partial_line_hits_total_deadline_and_preserves_bytes(self):
        clock=[0]
        class Trickled:
            status=200
            def getheader(self,key):return 'text/event-stream; charset=utf-8'
            def read1(self,limit):clock[0]+=450;return b'da'
        receive=Mock()
        with patch.object(C.time,'monotonic',side_effect=lambda:clock[0]):
            with self.assertRaisesRegex(RuntimeError,'deadline') as caught:
                C.read_sse(Trickled(),maximum=1,receive_socket=receive)
        self.assertEqual(base64.b64decode(caught.exception.client_partial_response['raw_sse_base64']),b'dada')
        self.assertEqual([call.args[0] for call in receive.settimeout.call_args_list],[900,450])

    def test_partial_stream_refusal_explicitly_closes_detached_response(self):
        class Reply(io.BytesIO):
            status=200
            def getheader(self,key):return 'text/event-stream; charset=utf-8'
        reply=Reply(b'data: invalid\n\n');connection=Mock();connection.sock=Mock()
        def detach():connection.sock=None;return reply
        connection.getresponse.side_effect=detach
        with patch.object(C.http.client,'HTTPConnection',return_value=connection):
            with self.assertRaises(ValueError) as caught:
                C.exchange(('127.0.0.1',1234),'POST','/v1/chat/completions',payload={'stream':True,'max_tokens':1},session='test')
        self.assertTrue(reply.closed);connection.close.assert_called_once()
        self.assertTrue(caught.exception.client_partial_response['raw_sse_base64'])

    def test_partial_stream_is_persisted_before_exercise_halts(self):
        fixture=ExerciseTests('test_actual_plan_and_full_flow');fixture.vectors=self.vectors;fixture.codec=self.codec;fixture.setUp()
        transport=fixture.transport
        def partial(address,method,path,**kwargs):
            response=transport(address,method,path,**kwargs)
            if response['status']==200 and kwargs.get('payload',{}).get('stream'):
                return self.parse(self.wire(self.vectors['rows'][0]).removesuffix(b'data: [DONE]\n\n'))
            return response
        with self.assertRaisesRegex(RuntimeError,'premature EOF') as caught:
            C.exercise(('127.0.0.1',1234),self.vectors,self.codec,native_reader=lambda rid:fixture.native[rid],
                guard=lambda:None,persist=lambda name,row:fixture.saved.__setitem__(name,row),transport=partial)
        self.assertEqual(fixture.turn,1);self.assertNotIn('01-native.json',fixture.saved)
        self.assertEqual(fixture.saved['01-http.json']['partial_response'],caught.exception.client_partial_response)


if __name__=='__main__':unittest.main()
