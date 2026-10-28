import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import colocated_control as c


def adapter():
    spec=importlib.util.spec_from_file_location('actual_adapter_cpu_test',c.ADAPTER)
    a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a);return a

class ControlTests(unittest.TestCase):
    def test_native_argv_legacy_launch_cap_and_no_pipeline(self):
        argv=['native','--rank','0','--max-new','512','--target-split','23',
              '--pipeline-stage','0','--pipeline-boundaries','0,23,48',
              '--pipeline-wavefront','--pipeline-live-draft','--pipeline-wavefront-verify-restore',
              '--recurrent-f32','--draft-mtp']
        a=c.native_argv(argv,Path('/output'),0)
        self.assertEqual(c.base.option(a,'--max-new'),'128')
        self.assertEqual(c.base.option(a,'--target-split'),'23')
        self.assertFalse(any(x.startswith('--pipeline-') for x in a))
        self.assertIn('--recurrent-f32',a);self.assertIn('--draft-mtp',a)
        with self.assertRaisesRegex(ValueError,'residual'):c.native_argv(argv+['--provider-only'],Path('/output'),0)

    def test_native_controller_actual_request_and_command_order(self):
        a=adapter()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);calls=[]
            raw=dict(tokens=list(range(512)),rank_trace=[],work_start=1,work_end=2,
                     stats=dict(hits=1,guesses=2),decode_intervals=2,decode_wall_ms=20)
            (p/'native-result.json').write_text(json.dumps(raw))
            b=NS(shared_path=p/'shared.bin',trace=[],a=NS(draft_fault='none'),device=True,
                 start=lambda *x:calls.append(('start',*x)),wait=lambda *x:calls.append(('wait',*x)))
            r=a.NativeController(b,a.BASE.Draft('mtp'),True,False,prefill=0,start=0).run([1,2],512,[248044,248046])
            self.assertEqual((p/'native-request.txt').read_text(),'3 512 1 0 2 0 2 1 2 248044 248046\n')
            self.assertEqual(calls,[('start',1,a.BASE.NATIVE),('start',0,a.BASE.NATIVE),('wait',0),('wait',1)])
            self.assertEqual(r['tokens'],list(range(512)))

    def test_actual_transport_finish_frames_and_teardown_receipts(self):
        a=adapter()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);wire=[];closed=[]
            t=a.Transport.__new__(a.Transport)
            for rank in (0,1):
                (p/f'rank{rank}').mkdir();(p/f'rank{rank}/receipt.json').write_text(json.dumps(dict(passed=True,rank=rank,teardown=[dict(safe_to_exit=True,in_flight=False,live_bytes=0)])))
            t.closed=False;t.stop_sent=False;t.children=[NS(pid=1,poll=lambda:0,returncode=0),NS(pid=2,poll=lambda:0,returncode=0)]
            t.pending=[False,False];t.finishing=set();t.seq=[4,8];t.out=p;t.check=lambda:None
            t.io=lambda rank,payload:wire.append((rank,a.BASE.REQUEST.unpack(payload)))
            t.mapping=NS(close=lambda:closed.append('map'));t.shared_path=p/'shared.bin';t.shared_path.touch()
            import os
            t.stop_read,t.stop_write=os.pipe();t.sockets=[];t.logs=[]
            t.close(True)
            self.assertEqual(wire,[(0,(a.BASE.FINISH,0,0,0,0,5,0,0)),(1,(a.BASE.FINISH,0,0,0,0,9,0,0))])
            self.assertTrue(t.closed);self.assertEqual(closed,['map']);self.assertFalse(t.shared_path.exists())
            self.assertEqual(json.loads((p/'ownership.json').read_text())['returncodes'],[0,0])

    def timing(self):
        ids=list(range(512));r=dict(tokens=ids,decode_intervals=511,decode_wall_ms=5110,
           timing_rows=[dict(generated_index=i+1,token_id=i,completed_monotonic=10+i*.01) for i in ids])
        return ids,r
    def test_actual_schema_timing(self):
        ids,r=self.timing();v=c.native_timing(r,ids,9,16)
        self.assertAlmostEqual(v['first99_decode_tokens_per_second'],100)
        self.assertAlmostEqual(v['decode_tokens_per_second'],100)
    def test_missing_wrong_or_unbounded_timing_refuses(self):
        ids,r=self.timing()
        for change in (lambda r:r.pop('timing_rows'),lambda r:r['timing_rows'].pop(),
                       lambda r:r['timing_rows'][99].update(token_id=999),
                       lambda r:r['timing_rows'][99].update(completed_monotonic=float('nan')),
                       lambda r:r.update(decode_wall_ms=1),
                       lambda r:r['timing_rows'][0].update(completed_monotonic=8)):
            q=copy.deepcopy(r);change(q)
            with self.assertRaises((KeyError,ValueError)):c.native_timing(q,ids,9,16)

    def test_child_registered_before_identity_capture_failure(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);binary=p/'binary';binary.write_bytes(b'cpu-not-executable')
            receipt=p/'receipt.json';receipt.write_text(json.dumps(dict(binary=str(binary),binary_sha256=c.base.digest(binary),sources={})))
            config=p/'config.json';config.write_text(json.dumps(dict(build_receipt=str(receipt))))
            plan=dict(config=str(config),output=str(p/'output'),pins={},binary_sha256=c.base.digest(binary),
                seconds=1800,root_floor_bytes=27000000000,evidence_floor_bytes=2147483648,
                stages=[dict(bdf=str(i),environment={},argv=['binary','<channel-fd>','<stop-fd>']) for i in (0,1)])
            guard=NS(tracked_processes=[],identities={},lock=threading.Lock(),failed=None,
                signal_stop=threading.Event(),deadline=c.time.monotonic()+10,obs=NS(process_identity=lambda pid:None))
            child=NS(pid=123,poll=lambda:0)
            with patch('subprocess.Popen',return_value=child):
                a,tp=c.bind_adapter(plan,guard)
                self.assertEqual(a.subprocess.STDOUT,-2)
                self.assertEqual((tp['context'],tp['max_new']),(65536,512))
                diagnostic=dict(plan,context=4096,max_new=1)
                _,dp=c.bind_adapter(diagnostic,guard)
                self.assertEqual((dp['context'],dp['max_new']),(4096,1))
                self.assertEqual(a.command(tp,0,12,13),['binary','12','13'])
                with self.assertRaisesRegex(ValueError,'process identity'):a.subprocess.Popen(['binary'])
            self.assertEqual(guard.tracked_processes,[(0,child)])
            self.assertEqual(guard.identities,{})
            bad=copy.deepcopy(tp);bad['context']=4096
            with self.assertRaisesRegex(ValueError,'exact isolated'):a.validate_plan(bad)

    def test_actual_transport_constructor_fragmented_ready_and_clean_finish(self):
        import os,socket,time
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);out=p/'output';out.mkdir();binary=p/'binary';binary.write_bytes(b'CPU fixture')
            receipt=p/'receipt.json';receipt.write_text(json.dumps(dict(binary=str(binary),binary_sha256=c.base.digest(binary),sources={})))
            cfg=p/'config.json';cfg.write_text(json.dumps(dict(build_receipt=str(receipt))))
            specs=[dict(bdf=str(i),environment={k:str(p/f'cache{i}'/k) for k in ('SYCL_CACHE_DIR','NEO_CACHE_DIR','XDG_CACHE_HOME')},argv=['fake','<channel-fd>','<stop-fd>']) for i in (0,1)]
            plan=dict(config=str(cfg),output=str(out),pins={},binary_sha256=c.base.digest(binary),seconds=1800,
                root_floor_bytes=27000000000,evidence_floor_bytes=2147483648,stages=specs)
            guard=NS(tracked_processes=[],identities={},lock=threading.Lock(),failed=None,signal_stop=threading.Event(),
                deadline=time.monotonic()+10,obs=NS(process_identity=lambda pid:{'start_ticks':pid}))
            frames=[];threads=[];counter=[]
            def spawn(argv,**kwargs):
                rank=len(counter);counter.append(rank);state={'rc':None}
                proc=NS(pid=2000+rank,poll=lambda:state['rc'])
                # Base close reads .returncode only after the server consumed FINISH.
                proc.returncode=0
                dest=out/f'native/rank{rank}';dest.mkdir(parents=True,exist_ok=True)
                (dest/'census.json').write_text(json.dumps(dict(allocations=[dict(live=True,memory='device',bytes=1)],totals={'device':1})))
                (dest/'receipt.json').write_text(json.dumps(dict(passed=True,rank=rank,teardown=[dict(safe_to_exit=True,in_flight=False,live_bytes=0)])))
                peer=socket.socket(fileno=os.dup(int(argv[1])))
                def server():
                    ready=a.BASE.REPLY.pack(0,0,0,0,0,rank,0,0,0.,0.,0.,0.)
                    peer.sendall(ready[:7]);peer.sendall(ready[7:])
                    data=b''
                    while len(data)<32:data+=peer.recv(32-len(data))
                    frames.append((rank,a.BASE.REQUEST.unpack(data)));state['rc']=0;peer.close()
                th=threading.Thread(target=server);th.start();threads.append(th);return proc
            with patch('subprocess.Popen',side_effect=spawn),patch.object(c.os,'getpriority',return_value=19):
                a,tp=c.bind_adapter(plan,guard)
                t=a.Transport(tp,admit=lambda q:self.assertEqual(q,tp),check=lambda:None,
                    launch_hook=lambda pid:self.assertIn(pid,guard.identities))
                t.close(True)
            for th in threads:th.join(1);self.assertFalse(th.is_alive())
            self.assertEqual(sorted(frames),[(0,(a.BASE.FINISH,0,0,0,0,1,0,0)),(1,(a.BASE.FINISH,0,0,0,0,1,0,0))])
            self.assertEqual(len(guard.tracked_processes),2)
            self.assertTrue(t.closed)

if __name__=='__main__':unittest.main()
