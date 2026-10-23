"""Qualified-module CPU mocks only; no native owner or network connection."""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import Mock,patch
from streaming_v1 import host_probe as P
from streaming_v1.test_engine import Front as BaseFront
import test_checkpoint_engine as F

class Front(BaseFront):
    def __init__(self,store,trusted):
        super().__init__(store,trusted);self.completed_controls=0
        self.ready.update(context=64,vocab=16)
    def dispose(self,*args):
        row=super().dispose(*args);self.completed_controls+=1;return row

class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.codec=P.PinnedChatCodec()
    def make(self):
        trusted=F.identity();trusted['geometry'].update(context=64,vocab=16,eos=15)
        store=F.Store();front=Front(store,trusted)
        engine=P.E.StreamingCheckpointEngine(front,store,root=store.root,expected_identity=trusted,
            admitted_contract='v1.2+p198',save_size_bound_bytes=8192,storage_available=lambda p:1000000,floor_bytes=1000)
        policies=[F.parking.Parking(engine,lambda m:m,lambda m:list(m[0]['tokens']),budget_bytes=b,
            accepted_contracts={('experimental-postreply-front','v1.2+p198')}) for b in (8192,0)]
        return P.FixtureFacade(engine,policies,self.codec,lambda:None,deadline=time.monotonic()+10),front
    def test_actual_decoder_tiny_ids_save_release_callback_order(self):
        service,front=self.make();texts=[]
        for n,row in enumerate(P.ROWS):
            front.generated=row['generated'];pieces=[]
            answer=service.stream(P.payload(row),session=row['session'],request_id=f'r{n}',on_delta=pieces.append)
            self.assertTrue(answer['stream_passed']);self.assertEqual(''.join(pieces),self.codec.decode(row['generated']))
            texts.append(''.join(pieces))
        self.assertEqual(texts,['!!!!','""""']);self.assertEqual([c[0] for c in front.calls],['RUN','SAVE','RUN','RELEASE'])
        self.assertEqual([e['controls'] for e in service.timeline if e['event']=='token-callback'],[0]*4+[1]*4)
        self.assertEqual(len(front.saved_tokens),1);self.assertIsNone(front.pending)
    def test_observer_failure_disposes_then_halts_fixture(self):
        service,front=self.make();front.generated=[0]*4;failure=OSError('observer failed')
        with self.assertRaises(OSError) as caught:
            service.stream(P.payload(P.ROWS[0]),session='alpha',request_id='r',on_delta=lambda t:(_ for _ in ()).throw(failure))
        self.assertIs(caught.exception,failure);self.assertEqual([c[0] for c in front.calls],['RUN','SAVE'])
        with self.assertRaises(OSError) as again:service.validate(P.payload(P.ROWS[0]))
        self.assertIs(again.exception,failure)
    def test_wrong_payload_session_and_production_geometry_refused(self):
        service,front=self.make()
        with self.assertRaises(P.ChatRequestError):service.validate(P.payload(P.ROWS[1]))
        with self.assertRaises(P.ChatRequestError):service.stream(P.payload(P.ROWS[0]),session='wrong',request_id='r',on_delta=lambda t:None)
        self.assertEqual(front.calls,[])
        service.engine.context=4096
        with self.assertRaisesRegex(RuntimeError,'tiny fixture'):P.FixtureFacade(service.engine,[],self.codec,lambda:None,deadline=1)
    def test_native_failure_keeps_original_after_observer_failure(self):
        service,front=self.make();front.generated=[0]*4;front.ambiguous_save=True
        with self.assertRaisesRegex(OSError,'SAVE acknowledgement') as caught:
            service.stream(P.payload(P.ROWS[0]),session='alpha',request_id='r',on_delta=lambda t:(_ for _ in ()).throw(ValueError('observer')))
        self.assertIs(service.failure,caught.exception);self.assertEqual([c[0] for c in front.calls],['RUN','SAVE'])

class ClientTests(unittest.TestCase):
    def wire(self):
        def event(delta,finish=None,usage=None):
            row=dict(id='chatcmpl-r',model=P.MODEL,choices=[dict(delta=delta,finish_reason=finish)])
            if usage is not None:row['usage']=usage
            return b'data: '+json.dumps(row).encode()+b'\n\n'
        return (b'HTTP/1.0 200 OK\r\nContent-Type: text/event-stream\r\n\r\n'+event(dict(role='assistant',content=''))+
            event(dict(content='!!!!'))+event({},'length',dict(prompt_tokens=3,completion_tokens=4,total_tokens=7))+b'data: [DONE]\n\n')
    def test_split_sse_complete_and_receive_time_claim_limited(self):
        raw=self.wire();conn=Mock();conn.recv.side_effect=[raw[:40],raw[40:77],raw[77:],b'']
        reply=P.request_sse(('127.0.0.1',1234),P.ROWS[0],connect=Mock(return_value=conn))
        turn=dict(completion=dict(id='chatcmpl-r',choices=[dict(message=dict(content='!!!!'))],usage=dict(prompt_tokens=3,completion_tokens=4,total_tokens=7)),disposition_monotonic=0)
        self.assertFalse(P.check_sse(reply,turn)['first_text_received_before_disposition']);conn.sendall.assert_called_once();conn.close.assert_called_once()
    def test_partial_sse_retained_with_primary_read_error_and_close_error(self):
        raw=self.wire().split(b'data: [DONE]')[0];conn=Mock();error=OSError('read original')
        conn.recv.side_effect=[raw,error];conn.close.side_effect=OSError('close secondary')
        with self.assertRaises(OSError) as caught:P.request_sse(('127.0.0.1',1234),P.ROWS[0],connect=Mock(return_value=conn))
        self.assertIs(caught.exception,error);self.assertEqual(bytes.fromhex(error.stream_partial['raw_http_hex']),raw)
        self.assertIn('close secondary',' '.join(error.__notes__))
    def test_no_done_and_nonloopback_refused_without_retry(self):
        conn=Mock();conn.recv.side_effect=[self.wire().replace(b'data: [DONE]\n\n',b''),b'']
        with self.assertRaisesRegex(RuntimeError,'terminal') as caught:P.request_sse(('127.0.0.1',1234),P.ROWS[0],connect=Mock(return_value=conn))
        self.assertTrue(caught.exception.stream_partial['frames']);conn.sendall.assert_called_once()
        with self.assertRaisesRegex(RuntimeError,'loopback'):P.request_sse(('localhost',1234),P.ROWS[0],connect=Mock(side_effect=AssertionError('no connection')))

class CleanupTests(unittest.TestCase):
    def setUp(self):self.addCleanup(P.RETAINED.clear)
    def owned(self):
        child=Mock();child.poll.return_value=0
        thread=Mock();thread.is_alive.return_value=False
        return dict(stop=threading.Event(),owner=child,thread=thread,store=Mock(),server=Mock(),stderr=Mock(),launch_uncertain=False)
    def test_original_error_and_busy_owner_store_retained_one_sigterm(self):
        owned=self.owned();owned['owner'].poll.return_value=None
        owned['owner'].wait.side_effect=subprocess.TimeoutExpired('tiny',65);error=OSError('original');result={}
        self.assertIs(P.cleanup(owned,result,error),error);self.assertTrue(result['retained']);owned['store'].close.assert_not_called()
        owned['owner'].send_signal.assert_called_once_with(signal.SIGTERM)
        P.cleanup(owned,result,error);owned['owner'].send_signal.assert_called_once()
    def test_poll_failure_preserves_original_and_uncertain_resources(self):
        owned=self.owned();owned['owner'].poll.side_effect=OSError('status unreadable');error=RuntimeError('first')
        result={};self.assertIs(P.cleanup(owned,result,error),error);self.assertTrue(result['retained'])
        owned['store'].close.assert_not_called();owned['owner'].send_signal.assert_not_called()
        self.assertIn('status unreadable',' '.join(error.__notes__))
    def test_uncertain_thread_start_or_popen_never_closes_store(self):
        for field in ('thread_start_uncertain','launch_uncertain'):
            owned=self.owned();owned[field]=True;result={};error=RuntimeError('startup uncertain')
            self.assertIs(P.cleanup(owned,result,error),error);self.assertTrue(result['retained']);owned['store'].close.assert_not_called()
    def test_clean_owner_handler_close_store_and_first_cleanup_error(self):
        owned=self.owned();failure=OSError('store close');owned['store'].close.side_effect=failure;result={}
        self.assertIs(P.cleanup(owned,result,None),failure);self.assertFalse(result['retained']);owned['server'].server_close.assert_called_once()

class PlanTests(unittest.TestCase):
    def test_actual_pinned_plan_and_exact_argv_interception(self):
        with patch.object(P,'OUTPUT',P.B.PACKET/'build'/('engine-integration-streaming-test-'+uuid.uuid4().hex)):
            spec=P.plan()
        self.assertFalse(spec['production_service_exercised']);self.assertEqual(spec['expected_controls'],['SAVE','RELEASE'])
        self.assertEqual(spec['binary_sha256'],'41cbb6c4ad3bf6626dfba24d3bbd9d95d76b512102e8b94c164e9d421b3c40ca')
        child=object();popen=Mock(return_value=child)
        self.assertIs(P.H.start_owner(spec,{'OMP_NUM_THREADS':'2'},None,popen=popen),child)
        self.assertEqual(popen.call_args.args[0],spec['argv']);self.assertIn('--pipeline-mini',spec['argv'])
        bad=copy.deepcopy(spec);bad['native_request_limit']=2
        with self.assertRaises(RuntimeError):P.H.start_owner(bad,{},None,popen=Mock(side_effect=AssertionError('no launch')))
    def test_occupied_root_wrong_interpreter_and_module_origin_refuse(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(P,'OUTPUT',Path(tmp)):
            with self.assertRaisesRegex(RuntimeError,'fresh'):P.plan()
        with patch.object(P.sys,'executable','/usr/bin/python3'):
            with self.assertRaisesRegex(RuntimeError,'interpreter'):P.plan()
        with patch.object(P.H,'__file__','/tmp/ambient.py'):
            with self.assertRaisesRegex(RuntimeError,'origin'):P.plan()
    def test_qualified_module_plan_smoke_no_native(self):
        env=dict(os.environ,PYTHONPATH=str(P.HERE.parent),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
        cp=subprocess.run([sys.executable,'-B','-m','streaming_v1.host_probe','--plan'],env=env,capture_output=True,text=True,timeout=30)
        if os.path.lexists(P.OUTPUT):
            self.assertNotEqual(cp.returncode,0);self.assertIn('fresh fixed streaming scratch required',cp.stderr)
        else:
            self.assertEqual(cp.returncode,0,cp.stderr);row=json.loads(cp.stdout);self.assertFalse(row['native_executed'])
        cp=subprocess.run([sys.executable,'-B',str(P.HERE/'host_probe.py'),'--plan'],env=env,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(cp.returncode,0);self.assertIn('direct script invocation is refused',cp.stderr)

if __name__=='__main__':unittest.main()
