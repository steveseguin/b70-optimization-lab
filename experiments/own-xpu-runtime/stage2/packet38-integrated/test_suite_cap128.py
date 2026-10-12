#!/usr/bin/python3 -B
"""CPU-only cap/clock/exactness regressions and WS/WSs mini-rank rehearsals.

Device prerequisites and host-health inputs are mocks. The sealed GNU host
binary runs only its mini model; no device binary or real model is executed.
"""
import contextlib
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import time
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import pipeline
import storage
import suite
import window
from test_receipt_metadata import run_gates

P=Path(__file__).resolve().parent
E=P/'evidence/20261012-suite128-wrapper'
RESULTS=[]

class CpuWatch:
    def __init__(self,*args):self.launched=[];self.cancelled=[]
    def check(self):pass
    def mark_launched(self,pid):pass  # CPU ranks only, no device launches
    def latch(self,error):pass
    def postflight(self):pass

def mock_rank():
    """Protocol-only fixture producer, never model/device execution."""
    def arg(name):return sys.argv[sys.argv.index(name)+1]
    rank=int(arg('--rank'));initial=Path(arg('--output'));initial.mkdir(parents=True,exist_ok=True)
    output=initial;shared=Path(arg('--shared')).parent
    cap=int(arg('--max-new'));assert cap in (64,128) and '--mini' in sys.argv
    sock=socket.socket(fileno=int(arg('--channel')))
    def reply(seq):
        now=time.monotonic();sock.sendall(pipeline.REPLY.pack(0,7,0,0,seq,rank,0,0,0.,0.,now,now))
    reply(0)
    while True:
        raw=b''
        while len(raw)<pipeline.REQUEST.size:
            chunk=sock.recv(pipeline.REQUEST.size-len(raw))
            if not chunk:return
            raw+=chunk
        op,token,position,fixture,spec,seq,_,_=pipeline.REQUEST.unpack(raw)
        if op==pipeline.FINISH:
            pipeline.save(initial/'receipt.json',dict(passed=True,rank=rank,mock_rank=True,
                teardown=[dict(safe_to_exit=True,in_flight=0,live_bytes=0)]))
            return
        if op==suite.RESET:
            state=output/'state-0';state.mkdir(parents=True,exist_ok=True)
            pipeline.save(state/'state.json',dict(buffers={}))
            output=Path((initial/f'reset-{seq}.txt').read_text().splitlines()[0]);output.mkdir(parents=True,exist_ok=True)
        elif op==pipeline.NATIVE:
            values=list(map(int,(shared/'native-request.txt').read_text().split()))
            mode,count,overlap,dumps,np,ns,ne=values[:7]
            assert count<=cap
            for step in range(1,min(count,8)+1):
                directory=output/f'step{step}';directory.mkdir(exist_ok=True)
                for layer in range(rank*2,rank*2+2):(directory/f'layer-{layer:02}.bf16').write_bytes(bytes([step,layer])*64)
            if rank==0:
                start=time.monotonic();stamps=[start+.001+.001*i for i in range(count)]
                pipeline.save(shared/'native-result.json',dict(tokens=[7]*count,guess_sequence=[],guess_rows=[],draft_rows=[],
                    stats=dict(guesses=count-1 if mode==3 else 0,hits=count-1 if mode==3 else 0,misses=0,no_guess=0,redo_ms=0.),
                    rank_trace=[],work_start=start,work_end=stamps[-1]+.001,prompt_wall_ms=(stamps[0]-start)*1000,
                    decode_wall_ms=(stamps[-1]-stamps[0])*1000,decode_intervals=count-1,
                    timing_rows=[dict(generated_index=i+1,token_id=7,completed_monotonic=t) for i,t in enumerate(stamps)]))
        else:raise AssertionError('unsupported mock command '+str(op))
        reply(seq)

class Gates(unittest.TestCase):
    def setUp(self):
        storage.admit(40_000_000)
        self.tmp=tempfile.TemporaryDirectory(prefix='suite128-test-',dir=P/'build')
        self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()

    def test_manifest_admission(self):
        for cap in (64,128):
            m=dict(arithmetic='iq3-p17-detmath-v2',context=256,token_cap=cap,
                   prompts=[dict(prompt_id='a',prompt_tokens=256-cap)])
            self.assertEqual(suite.validate_manifest(m),cap)
            m['prompts'].append(dict(prompt_id='overflow',prompt_tokens=257-cap))
            with self.assertRaisesRegex(ValueError,'exceeds context'):suite.validate_manifest(m)
        for cap in (0,63,65,100,127,129,256,True,64.0,'128'):
            with self.assertRaises(ValueError):suite.validate_manifest(dict(arithmetic='iq3-p17-detmath-v2',token_cap=cap))
        for context in (128,257,512):
            with self.assertRaises(ValueError):suite.validate_manifest(dict(arithmetic='iq3-p17-detmath-v2',token_cap=128,context=context,prompts=[]),context)

    def test_clock_formula(self):
        # t1=12, t64=138, t100=210: 63/126 = 99/198 = 0.5 tok/s.
        # Request start=10, end=268; TTFT=2s; wall rate=128/258.
        transport=SimpleNamespace(work_start=10.,work_end=268.,device=True)
        def result(n):
            return dict(tokens=[7]*n,stats=dict(guesses=90,hits=70),
                        timing_rows=[dict(token_id=7,completed_monotonic=12.+2*i) for i in range(n)])
        r=pipeline.request_timing_metadata(result(128),transport,[1,2,3],128)
        self.assertEqual((r['decode_tok_s'],r['submission_tok_s']),(0.5,0.5))
        self.assertEqual((r['decode_intervals'],r['submission_intervals'],r['submission_event_count']),(63,99,100))
        self.assertEqual(r['submission_last_completed_monotonic'],210.)
        self.assertEqual(r['ttft_ms'],2000.)
        self.assertEqual(r['wall_tok_s'],128/258)
        self.assertEqual((r['prompt_tokens'],r['output_tokens'],r['ended_early'],r['guesses'],r['hits']),(3,128,False,90,70))
        self.assertEqual(len(r['generated_token_completion_timestamps']),128)
        altered=result(128)
        for row in altered['timing_rows'][100:]:row['completed_monotonic']=220.
        changed=pipeline.request_timing_metadata(altered,transport,[1],128)
        self.assertEqual((changed['decode_tok_s'],changed['submission_tok_s']),(.5,.5))
        self.assertEqual(r['decode_wall_ms'],126000.)
        for n in (1,64,99,100,104):
            r=pipeline.request_timing_metadata(result(n),transport,[1],128)
            self.assertEqual(r['submission_window_available'],n>=100)
            self.assertEqual(r['submission_tok_s'],0.5 if n>=100 else None)
            self.assertTrue(r['ended_early'])
        eos=result(100);eos['tokens'][-1]=suite.EOS[0];eos['timing_rows'][-1]['token_id']=suite.EOS[0]
        self.assertEqual(pipeline.request_timing_metadata(eos,transport,[1],128)['submission_tok_s'],0.5)
        transport.device=False
        r=pipeline.request_timing_metadata(result(128),transport,[1],128)
        self.assertIsNone(r['submission_tok_s'])
        self.assertTrue(run_gates()['passed'])
        RESULTS.append(dict(case='hand-computed metric',t1=12,t64=138,t100=210,legacy_tok_s=.5,submission_tok_s=.5,ttft_ms=2000,passed=True))

    def test_summary_medians(self):
        rows=[dict(prompt_id=p,repeat=i,passed=True,decode_tok_s=v,submission_tok_s=v*2,submission_window_available=True)
              for p,i,v in [('a',1,1),('a',2,3),('a',3,5),('b',1,9)]]
        r=suite.summarize(rows,True,2)
        self.assertEqual(r['decode_median_tok_s'],4)
        self.assertEqual(r['decode_median_of_prompt_medians_tok_s'],6)
        self.assertEqual(r['submission_median_tok_s'],8)
        self.assertEqual(r['submission_median_of_prompt_medians_tok_s'],12)
        rows.append(dict(prompt_id='b',repeat=2,passed=False,decode_tok_s=999,submission_tok_s=999))
        r=suite.summarize(rows,True,2)
        self.assertFalse(r['passed']);self.assertFalse(r['submission_all_requests_have_100_events'])
        self.assertEqual(r['submission_median_tok_s'],8)

    def test_exact_oracles_and_corruption(self):
        for cap in (64,128):
            source=P.parent/('suite-inputs-20261012-cap128' if cap==128 else 'suite-inputs-20261012')/'suite-manifest.json'
            manifest=json.loads(source.read_text());suite.validate_manifest(manifest)
            entry=manifest['prompts'][0];oracle=suite.ROOT/entry['oracle_directory']
            checker=suite.RetainedFixtureChecker(suite.checker_module(suite.CHECKER128)) if cap==128 else suite.checker_module()
            dest=self.root/f'actual-{cap}';dest.mkdir()
            tokens=json.loads((oracle/'result.json').read_text())['tokens']
            receipt=dict(schema='own-runtime.iq3.packet26.run.v1',passed=True,arithmetic=manifest['arithmetic'],tokens=tokens)
            pipeline.save(dest/'receipt.json',receipt)
            for step in range(1,9):shutil.copytree(oracle/f'step{step}',dest/f'step{step}',copy_function=os.link)
            self.assertEqual(checker.check_prompt(dest,oracle,entry,suite.ROOT),(cap,384))
            checked=suite.compare_request(dest,dict(passed=True),entry,checker,cap)
            self.assertEqual(checked['fixture_steps_checked'],list(range(1,9)))
            self.assertEqual(checked['fixture_steps_not_retained_by_this_binary'],list(range(97,105)) if cap==128 else [])
            bad=copy.deepcopy(receipt);bad['tokens'][-1]^=1;pipeline.save(dest/'receipt.json',bad)
            with self.assertRaisesRegex(ValueError,'tokens differ'):checker.check_prompt(dest,oracle,entry,suite.ROOT)
            pipeline.save(dest/'receipt.json',receipt)
            fixture=dest/'step8/layer-47.bf16';raw=fixture.read_bytes();fixture.unlink();fixture.write_bytes(bytes([raw[0]^1])+raw[1:])
            # Rehash the corrupt candidate to exercise byte equality, not just metadata.
            meta=dest/'step8/layers.jsonl';records=[json.loads(line) for line in meta.read_text().splitlines()]
            records[-1]['sha256']=pipeline.sha(fixture);meta.unlink();meta.write_text(''.join(json.dumps(r)+'\n' for r in records))
            with self.assertRaises(ValueError):checker.check_prompt(dest,oracle,entry,suite.ROOT)
            outcome=suite.compare_request(dest,dict(passed=True),entry,checker)
            self.assertFalse(outcome['passed'])
            self.assertEqual(pipeline.sha(oracle/'step8/layer-47.bf16'),__import__('hashlib').sha256(raw).hexdigest())
            RESULTS.append(dict(case='oracle-derived comparison',token_cap=cap,tokens=cap,fixture_files=384,corrupt_last_token_rejected=True,corrupt_rehashed_fixture_rejected=True,late_fixtures_not_required=True,real_model_execution=False,checker_sha256=checker.source_sha256,passed=True))

    def test_window_suite_end_to_end(self):
        real_run=pipeline.run
        binary=P/'build/gnu-host/own-rt-iq3'
        affinity=sorted(os.sched_getaffinity(0))
        def prerequisites(path,name,identity):
            return dict(identity,passed=True,window=name,pids=[101,102] if name=='K1a' else [103,104],
                        candidate_dispatch_sha256=pipeline.sha(P/'dispatch-p38.json'),dispatch_sha256=pipeline.sha(P/'dispatch-p38.json'))
        for cap,backend in ((64,'native-mini'),(64,'mock-rank'),(128,'mock-rank')):
            binary=P/'build/gnu-host/own-rt-iq3' if backend=='native-mini' else P/'test_suite_cap128.py'
            manifest=self.root/f'manifest-{cap}.json'
            pipeline.save(manifest,dict(arithmetic='iq3-p17-detmath-v2',token_cap=cap,context=256,complete=True,
                prompts=[dict(prompt_id=name,prompt_tokens=len(tokens),mini_tokens=tokens,input_bundle='unused-mini')
                         for name,tokens in [('alpha',[2,5,3,7,1]),('beta',[1,2,1])]]))
            for name in ('WS','WSs'):
                dest=self.root/f'{name}-{cap}-{backend}'
                def cpu_run(args,env,check,failure_hook,launch_hook):
                    self.assertEqual(args.tokens,cap)
                    self.assertEqual(args.draft,'mtp' if name=='WS' else 'none')
                    args.device=False;args.mini=True;args.binary=binary;args.native_nice=19;args.host_memory='resident';args.dispatch=None
                    # Read real priority in suite; only window's nice-0 admission is mocked.
                    with patch.object(window.os,'getpriority',return_value=19):
                        return real_run(args,env,check,failure_hook,launch_hook)
                argv=['window.py','--authorized-device-window','--window',name,'--card','0','--output',str(dest),
                      '--controller','native','--suite-manifest',str(manifest),'--repeat','1','--dispatch',str(P/'dispatch-p38.json')]
                for key in ('k0','k1a','k1b','k2','w0p','kd'):argv+=['--'+key,str(self.root/('mock-'+key))]
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch('sys.argv',argv))
                    stack.enter_context(patch.object(window,'environment_gate',return_value={'native':{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'}}))
                    stack.enter_context(patch.object(window.os,'getpriority',return_value=0))
                    stack.enter_context(patch.object(window,'prerequisites',prerequisites))
                    stack.enter_context(patch.object(window,'foreign_engines',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(window,'memory_snapshot',return_value={'MemAvailable':128*1024**3}))
                    stack.enter_context(patch.object(window,'Watch',CpuWatch))
                    stack.enter_context(patch.object(window,'ldd_preflight',return_value={'cpu_mock':True}))
                    stack.enter_context(patch.object(pipeline,'run',cpu_run))
                    rc=window.main()
                    record=json.loads((dest/'window.json').read_text())
                    if rc:
                        import gzip
                        logs={str(f.relative_to(dest)):gzip.decompress(f.read_bytes()).decode() for f in dest.glob('run/ranks/*.log.gz')}
                        pipeline.save(E/'failed-window.json',dict(record=record,rank_logs=logs))
                    self.assertEqual(rc,0,record.get('error'))
                record=json.loads((dest/'window.json').read_text());summary=json.loads((dest/'run/summary.json').read_text())
                self.assertTrue(record['passed']);self.assertFalse(record['device_executed'])
                self.assertTrue(summary['passed']);self.assertEqual(summary['token_cap'],cap)
                self.assertEqual(len(summary['rows']),2)
                for rank in (0,1):
                    launch=json.loads((dest/f'run/ranks/rank{rank}-launch.json').read_text())
                    self.assertEqual(launch['argv'][launch['argv'].index('--max-new')+1],str(cap))
                    self.assertIn('--mini',launch['argv']);self.assertFalse(launch['device_executed'])
                    self.assertEqual(launch['cpu_affinity'],affinity)
                for row in summary['rows']:
                    self.assertEqual(row['tokens'],cap)
                    self.assertEqual(len(row['generated_token_completion_timestamps']),cap)
                    self.assertEqual(row['submission_window_available'],cap==128)
                    receipt=json.loads((dest/'run'/row['receipt']).read_text())
                    self.assertEqual(receipt['decode_intervals'],63)
                    self.assertEqual(receipt['submission_intervals'],99 if cap==128 else 0)
                    self.assertAlmostEqual(receipt['ttft_ms'],receipt['prompt_wall_ms'],places=5)
                    self.assertFalse(receipt['ended_early'])
                self.assertEqual(sorted(os.sched_getaffinity(0)),affinity)
                summary['test_scope']=backend+' only; mocked device prerequisites/health; not device qualification or a speed result'
                pipeline.save(E/f'{name}-{cap}-{backend}-summary.json',summary)
                RESULTS.append(dict(case='window -> pipeline -> suite -> ranks -> summary',backend=backend,window=name,token_cap=cap,requests=2,repeat=1,passed=True,device_executed=False,real_model_execution=False,binary_sha256=pipeline.sha(binary),cpu_affinity=affinity,summary_sha256=pipeline.sha(E/f'{name}-{cap}-{backend}-summary.json')))

if __name__=='__main__':
    if '--rank' in sys.argv:
        mock_rank();raise SystemExit(0)
    storage.admit(40_000_000);E.mkdir(parents=True,exist_ok=True)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Gates))
    pipeline.save(E/'tests.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),device_executed=False,real_model_execution=False,results=RESULTS,
        source_sha256={n:pipeline.sha(P/n) for n in ('test_suite_cap128.py','suite.py','pipeline.py','window.py')}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
