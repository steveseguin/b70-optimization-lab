import copy,json,os,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import adapter as A

class Child:
    pid=99999999
    returncode=0
    def poll(self):return 0

class Backend:
    """Protocol mock consumed by the actual inherited NativeController."""
    def __init__(self,path):
        self.out=path;self.request_output=path;self.shared_path=path/'shared.bin';self.shared_path.write_bytes(bytes(A.BASE.SHARED));self.mapping=bytearray(A.BASE.SHARED)
        self.a=types.SimpleNamespace(mini=True,tokens=4,context=64,draft_rank=0,draft_fault='none');self.plan={'mini':True}
        self.pending=[False,False];self.seq=[0,0];self.trace=[];self.children=[Child(),Child()];self.device=False;self.calls=[];self.requests=0;self.wrong=False;self.fail=None
        for r in (0,1):(path/f'rank{r}').mkdir()
    def check_alive(self):
        if self.fail:raise self.fail
    def start(self,r,op):self.calls.append(('start',r,op));self.pending[r]=True;self.seq[r]+=1
    def wait(self,r):
        self.calls.append(('wait',r));self.pending[r]=False
        if not any(self.pending):
            self.requests+=1
            row={'rank_trace':[],'tokens':[2,3,4,5] if not(self.wrong and self.requests==2) else [2,3,4,6],'work_start':1.,'work_end':2.,'stats':{'guesses':2,'hits':1},'decode_intervals':3,'decode_wall_ms':1.}
            (self.out/'native-result.json').write_text(json.dumps(row))
    def call(self,r,op,**kw):
        self.calls.append(('call',r,op));self.seq[r]+=1
        if op==A.BASE.DUMP:
            p=self.request_output/f'rank{r}'/'state-2147483647';p.mkdir(parents=True,exist_ok=True);(p/'target.bin').write_bytes(b'exact')
        if op==11:
            p=self.out/f'rank{r}'/f'reset-{self.seq[r]}.txt';dest=Path(p.read_text().splitlines()[0]);dest.mkdir(parents=True)

class Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup();A.RETAINED.clear()
    def plan(self,mini=True):return A.build_plan(self.p/'run',mini=mini)
    def test_plan_only_and_exact_rank_binding(self):
        with patch.object(A.subprocess,'Popen',side_effect=AssertionError('no child')):p=self.plan(False)
        for r,argv in enumerate(p['rank_argv']):
            self.assertEqual(argv[argv.index('--card')+1],'0');self.assertIn('--gsq-packed',argv);self.assertNotIn('--selection',argv);self.assertNotIn('--dispatch',argv)
            self.assertEqual(p['environment'][r]['HOME'],'/home/steve');self.assertEqual(p['environment'][r]['FilterBdfPath'],A.BDFS[r])
        self.assertIn('--draft-mtp',p['rank_argv'][0]);self.assertNotIn('--draft-mtp',p['rank_argv'][1]);self.assertEqual(p['storage']['raw_state_bytes'],462885000)
    def test_external_output_only_rank_paths(self):
        ep=self.p/'external';ep.mkdir();p=A.build_plan(self.p/'control',evidence_output=ep/'evidence')
        self.assertEqual(p['rank_argv'][0][p['rank_argv'][0].index('--output')+1],str(ep/'evidence/rank0'))
        self.assertEqual(p['rank_argv'][0][p['rank_argv'][0].index('--shared')+1],str(self.p/'control/shared.bin'))
        self.assertTrue(p['environment'][0]['SYCL_CACHE_DIR'].startswith(str(self.p/'control')))
    def test_dirty_parent_and_limits_refuse(self):
        for kw in ({'max_new':0},{'seconds':7201}):
            with self.assertRaises(ValueError):A.build_plan(self.p/'run',**kw)
        self.p.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'private'):self.plan()
        self.p.chmod(0o700)
    def test_plan_mutation_before_any_spawn(self):
        p=self.plan();p['rank_argv'][0].append('--legacy')
        with patch.object(A.subprocess,'Popen',side_effect=AssertionError('no spawn')):
            with self.assertRaisesRegex(ValueError,'changed'):A.validate_plan(p)
    def test_real_historical_host_source_binding_read_only(self):
        p=self.plan()
        with patch.object(A.subprocess,'Popen',side_effect=AssertionError('no executable')):
            build=A.validate_plan(p)
        self.assertEqual(build['mode'],'host');self.assertTrue(build['passed'])
    def test_storage_refusal_before_any_process(self):
        p=self.plan(False)
        with patch.object(A.shutil,'disk_usage',return_value=types.SimpleNamespace(free=0)),patch.object(A.subprocess,'Popen',side_effect=AssertionError('no executable')):
            with self.assertRaisesRegex(ValueError,'storage'):A.storage_guard(p)
    def test_constructor_actual_popen_boundary(self):
        p=self.plan();t=A.Transport.__new__(A.Transport);seen=[]
        with patch.object(A,'validate_plan',return_value={}),patch.object(A.Transport,'receive',return_value={}),patch.object(A.subprocess,'Popen',side_effect=lambda *a,**k:(seen.append((a,k)) or Child())):
            t.__init__(p,admit=lambda _:None,check=lambda:None,launch_hook=lambda _:None)
        self.assertEqual(len(seen),2);self.assertEqual(t.launch_attempts,2);self.assertFalse(t.spawn_uncertain)
        for r,(args,kw) in enumerate(seen):self.assertEqual(kw['env'],p['environment'][r]);self.assertEqual(len(kw['pass_fds']),2)
        t.close(False);self.assertTrue(t.closed)
    def test_prelaunch_guard_no_process(self):
        with patch.object(A,'validate_plan',return_value={}),patch.object(A.subprocess,'Popen',side_effect=AssertionError('no spawn')):
            with self.assertRaisesRegex(RuntimeError,'guard'):A.Transport(self.plan(),admit=lambda _:None,check=lambda:(_ for _ in ()).throw(RuntimeError('guard')),launch_hook=lambda _:None)
        self.assertFalse((self.p/'run').exists())
    def test_uncertain_spawn_never_closes_resources(self):
        primary=RuntimeError('spawn uncertain');t=types.SimpleNamespace(spawn_uncertain=True,stop_write=7,stop=lambda _:None,close=lambda _:self.fail('close must not run'),children=[])
        with self.assertRaises(A.RetainedOwner) as e:A.cleanup_failure(t,primary)
        self.assertIs(e.exception.original,primary);self.assertIs(A.RETAINED[-1],t)
    def test_second_spawn_failure_retains_first_and_mapping(self):
        p=self.plan();t=A.Transport.__new__(A.Transport);primary=RuntimeError('second spawn')
        with patch.object(A,'validate_plan',return_value={}),patch.object(A.subprocess,'Popen',side_effect=[Child(),primary]):
            with self.assertRaises(RuntimeError) as e:t.__init__(p,admit=lambda _:None,check=lambda:None,launch_hook=lambda _:None)
        self.assertIs(e.exception,primary)
        with self.assertRaises(A.RetainedOwner):A.cleanup_failure(t,primary)
        self.assertFalse(t.mapping.closed);self.assertTrue(t.shared_path.exists());self.assertEqual(len(t.children),1)
        # Fixture proves no real spawn; explicitly release only its fake resources.
        t.spawn_uncertain=False;t.close(False)
    def test_poll_and_cleanup_errors_preserve_primary(self):
        primary=RuntimeError('primary');t=types.SimpleNamespace(spawn_uncertain=False,stop_write=1,stop=lambda _:(_ for _ in ()).throw(OSError('disk')),close=lambda _:(_ for _ in ()).throw(OSError('close')),children=[types.SimpleNamespace(poll=lambda:(_ for _ in ()).throw(OSError('poll')))])
        with self.assertRaises(A.RetainedOwner) as e:A.cleanup_failure(t,primary)
        self.assertIs(e.exception.original,primary);self.assertEqual(len(e.exception.secondary),3)
    def test_actual_nativecontroller_same_pair_reset_and_tokens(self):
        b=Backend(self.p);r=A.compare_attached(b,[2,5,3],4)
        self.assertTrue(r['passed']);self.assertEqual(b.requests,2);self.assertEqual([x for x in b.calls if x[0]=='call' and x[2]==11],[('call',0,11),('call',1,11)])
        self.assertEqual([x for x in b.calls if x[0]=='start'],[('start',1,10),('start',0,10)]*2)
        self.assertTrue((self.p/'none-result.json').exists());self.assertTrue((self.p/'mtp-result.json').exists())
        with self.assertRaisesRegex(ValueError,'already used'):A.compare_attached(b,[2],1)
    def test_mtp_mismatch_refuses_without_third_request(self):
        b=Backend(self.p);b.wrong=True
        with self.assertRaisesRegex(ValueError,'token mismatch'):A.compare_attached(b,[2],4)
        self.assertEqual(b.requests,2)
    def test_fault_no_request_and_original_object(self):
        b=Backend(self.p);b.fail=RuntimeError('fault')
        with self.assertRaises(RuntimeError) as e:A.compare_attached(b,[2],4)
        self.assertIs(e.exception,b.fail);self.assertEqual(b.requests,0)
    def test_reset_pending_refused(self):
        b=Backend(self.p);b.pending[0]=True
        with self.assertRaisesRegex(ValueError,'busy'):A.reset(b,self.p/'next')
        self.assertFalse((self.p/'next').exists())

if __name__=='__main__':unittest.main()
