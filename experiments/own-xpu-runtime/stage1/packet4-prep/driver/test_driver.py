"""CPU tests. Real vLLM never imported; devices are forbidden by the mocks."""
import ast
from contextlib import nullcontext
import copy
import importlib
import os
from pathlib import Path
import signal
import runpy
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

# Import once before temporary sys.modules mocks; removing a loaded torch
# module and reimporting its extension would itself be an invalid test setup.
import torch

import window_driver as w
import shutdown_guard as sg


def fake_vllm():
    for name in ('vllm', 'vllm.v1', 'vllm.v1.worker', 'vllm.v1.worker.xpu_worker', 'vllm.plugins',
                 'vllm.v1.utils','vllm.v1.engine','vllm.v1.engine.utils',
                 'vllm.v1.executor','vllm.v1.executor.multiproc_executor'):
        sys.modules[name] = types.ModuleType(name)
        if '.' in name:
            parent, attr = name.rsplit('.',1)
            setattr(sys.modules[parent],attr,sys.modules[name])
    sys.modules['vllm']._packet4_mock=True
    sys.modules['vllm'].__file__='/home/steve/src/vllm-current-main/vllm/__init__.py'
    sys.modules['vllm.v1.executor.multiproc_executor'].MultiprocExecutor=type('Executor',(),{})
    class Worker:
        def __init__(self, rank, vllm_config, **kw):
            self.rank, self.vllm_config = rank, vllm_config
            self.loads = self.calls = self.stops = 0
        def load_model(self):
            self.loads += 1
            return self.loads
        def execute_model(self, scheduler_output):
            self.calls += 1
            return self.model(torch.ones((2, 4), dtype=torch.bfloat16))
        def shutdown(self):
            self.stops += 1
    import torch
    sys.modules['vllm.v1.worker.xpu_worker'].XPUWorker = Worker
    sys.modules['vllm.plugins'].load_general_plugins = lambda: None
    return Worker


def subprocess_rank(root, rank):
    """Execute certified init_worker AST with dependencies mocked, then real hook transport."""
    fake_vllm()
    # Real spawn bootstrap execution, with all vLLM dependencies mocked.
    os.environ['PACKET4_SOURCE']='/home/steve/src/vllm-current-main'
    runpy.run_path(str(w.HERE/'server_entry.py'),run_name='__mp_main__')
    assert sys.modules['vllm.v1.utils'].shutdown is sg.request_and_wait
    assert sys.modules['vllm.v1.engine.utils'].shutdown is sg.request_and_wait
    assert sys.modules['vllm.v1.executor.multiproc_executor'].MultiprocExecutor._ensure_worker_termination is sg.wait_only
    from packet4_worker import ExtractionWorker
    import torch
    from extract_fixtures import Recorder
    from mock_comparator import mock_identity, EAGER
    source = Path('/home/steve/src/vllm-current-main/vllm/v1/worker/worker_base.py')
    w.require(w.sha(source) == w.read(w.PREREG)['source_pins']['vllm/v1/worker/worker_base.py'], 'test source drift')
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'WorkerWrapperBase')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'init_worker')
    fn.decorator_list = []
    # Only annotations/decorator dependencies are removed. Dispatch body unchanged.
    for n in ast.walk(fn):
        if isinstance(n, ast.arg):
            n.annotation = None
    fn.returns = None
    def resolve(name):
        module, attr = name.rsplit('.', 1)
        return getattr(importlib.import_module(module), attr)
    env = {'resolve_obj_by_qualname': resolve, 'set_current_vllm_config': lambda *_: nullcontext(),
           'logger': types.SimpleNamespace(warning_once=lambda *_: None)}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), 'exec'), env)
    config = types.SimpleNamespace(enable_trace_function_call_for_thread=lambda: None,
        parallel_config=types.SimpleNamespace(worker_cls='packet4_worker.ExtractionWorker', worker_extension_cls=None),
        model_config=types.SimpleNamespace(multimodal_config=None))
    wrapper = types.SimpleNamespace(rpc_rank=rank)
    env['init_worker'](wrapper, [{'rank': i, 'vllm_config': config} for i in range(4)])
    worker = wrapper.worker
    class Model(torch.nn.Module):
        def forward(self, x):
            self.result = x + 1
            return self.result
    def install(self):
        self.model = Model()
        self._packet4_recorder = Recorder(self._packet4_dir, 'flash-next', mock_identity(), EAGER,
                                         w.read(w.ORACLE), w.PROMPT_ID, max_bytes=1048576)
        spec = {'M': 2, 'N': 4, 'K': 4, 'layer': 0, 'rank': self.rank,
                'positions': [7, 8], 'valid_rows': [True, True], 'rows': [0, 1],
                'name': 'linear', 'location': 'mock.layer0', 'census_items': ['U3'],
                'arithmetic_order': 'original mock once', 'rounding_points': ['BF16'],
                'reference': None, 'expected': {}}
        self._packet4_stack.enter_context(self._packet4_recorder.hook(
            self.model, spec, lambda m,a,k: (a,k), lambda m,a,k,r: {'result':r}))
        w.write(self._packet4_dir / 'registered.json', {'rank': self.rank, 'registration_count': 1})
    with patch.object(ExtractionWorker, '_packet4_install', install):
        assert worker.load_model() == 1
        try:
            worker.load_model()
            raise AssertionError('duplicate registration accepted')
        except ValueError:
            pass
        out = worker.execute_model(types.SimpleNamespace(total_num_scheduled_tokens=2))
        assert out is worker.model.result and torch.equal(out, torch.full((2,4), 2, dtype=torch.bfloat16))
        assert worker.calls == worker.loads == 1 and not worker._packet4_in_target
        worker.shutdown()
        worker.shutdown()
        assert worker.stops == 1
        assert not worker.model._forward_hooks and not worker.model._forward_pre_hooks
    assert sys.modules['vllm']._packet4_mock


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='packet4-driver-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = time.time()
        self.boot = 'mock-boot'
        stamp = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(self.now-10))
        self.health = {'schema': 'ltx.four-card-health.v1', 'passed': True, 'boot_id': self.boot,
            'kernel': Path('/proc/sys/kernel/osrelease').read_text().strip(), 'start_utc': stamp, 'end_utc': stamp,
            'device_count': 4, 'cards': [{'device': f'xpu:{i}', 'pass': True} for i in range(4)],
            'journal_fault_lines_during_probe': [], 'fault_lines_earlier_this_boot': 0}
        w.write(self.root/'health.json', self.health)
        self.output = self.root / 'out'
        self.owner = {'schema': 'own-xpu-runtime.packet4.owner-window.v1', 'authorized': True,
            'boot_id': self.boot, 'host': 'steve-b70s', 'preregistration_sha256': w.sha(w.PREREG),
            'health_path': str(self.root/'health.json'), 'health_sha256': w.sha(self.root/'health.json'),
            'output': str(self.output), 'halt_resolved': True, 'issued_unix': self.now-30,
            'pci_ids': ['0000:23:00.0','0000:27:00.0','0000:43:00.0','0000:47:00.0'], 'firmware': 'mock',
            'expires_unix': self.now+3000, 'previous_teardown_completed_unix': self.now-400}
    def admit(self, **kw):
        with patch('socket.gethostname', return_value='steve-b70s'):
            w.verify_admission(kw.get('owner', self.owner), kw.get('health', self.health), self.boot,
                self.now, self.output, kw.get('rows', []), [self.root/'FAULT.json'])
    def test_valid(self): self.admit()
    def test_missing_authorization(self):
        with self.assertRaisesRegex(ValueError, 'authorization'): self.admit(owner={})
    def test_wrong_boot(self):
        self.owner['boot_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'host/boot'): self.admit()
    def test_expired_owner(self):
        self.owner['expires_unix'] = self.now-1
        with self.assertRaisesRegex(ValueError, 'window'): self.admit()
    def test_unresolved_halt(self):
        self.owner['halt_resolved'] = False
        with self.assertRaisesRegex(ValueError, 'halt'): self.admit()
    def test_fault_latch(self):
        (self.root/'FAULT.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'FAULT'): self.admit()
    def test_stale_health(self):
        self.health['end_utc'] = '2000-01-01 00:00:00 UTC'
        with self.assertRaisesRegex(ValueError, 'stale'): self.admit()
    def test_failed_health(self):
        self.health['passed'] = False
        with self.assertRaisesRegex(ValueError, 'health failed'): self.admit()
    def test_duplicate_health_card(self):
        self.health['cards'][3]['device'] = 'xpu:0'
        with self.assertRaisesRegex(ValueError, 'rank coverage'): self.admit()
    def test_health_fault(self):
        self.health['journal_fault_lines_during_probe'] = ['Fault response']
        with self.assertRaisesRegex(ValueError, 'journal fault'): self.admit()
    def test_earlier_faults_not_waived(self):
        self.health['fault_lines_earlier_this_boot'] = 1
        with self.assertRaisesRegex(ValueError, 'earlier boot'): self.admit()
    def test_gap(self):
        self.owner['previous_teardown_completed_unix'] = self.now-304.99
        with self.assertRaisesRegex(ValueError, 'gap'): self.admit()
    def test_reuse(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'reuse'): self.admit()
    def test_owner_seal(self):
        self.owner['preregistration_sha256'] = 'bad'
        with self.assertRaisesRegex(ValueError, 'pin'): self.admit()
    def test_running_ltx(self):
        with self.assertRaisesRegex(ValueError, 'process running'): self.admit(rows=[(91, 'python', 'python /app/ltx_server.py')])
    def test_running_worker(self):
        with self.assertRaisesRegex(ValueError, 'process running'): self.admit(rows=[(92, 'VLLM::Worker_TP0', '')])
    def test_running_server(self):
        with self.assertRaisesRegex(ValueError, 'process running'): self.admit(rows=[(93, 'python', 'vllm serve model')])
    def test_health_artifact_mutation(self):
        (self.root/'health.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'health pin'): self.admit()
    def test_foreign_output(self):
        self.owner['output'] = str(self.root/'other')
        with self.assertRaisesRegex(ValueError, 'output binding'): self.admit()


class MemoryRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='packet4-memory-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'approval.json'
        self.boot = 'synthetic-test-boot'
        self.floor = 133542784
        self.digest = w.sha(w.REVISION_DOC)
        self.receipt = {'schema': 'own-xpu-runtime.packet4.admission-revision.v1',
            'approved': True, 'approved_by': 'owner', 'host': 'steve-b70s', 'boot_id': self.boot,
            'revision_document_sha256': self.digest, 'minimum_mem_available_kib': self.floor,
            'owner_approval_text': w.approval_text(self.floor, self.digest)}
    def verify(self):
        w.write(self.path, self.receipt)
        with patch('socket.gethostname', return_value='steve-b70s'):
            return w.verify_memory_revision(self.path, self.boot)
    def test_approved_exact_document_and_floor(self):
        r = self.verify()
        self.assertEqual(r['minimum_mem_available_bytes'], self.floor * 1024)
        self.assertEqual(r['delta_from_a367_bytes'], 13542784 * 1024)
        self.assertEqual(r['receipt']['sha256'], w.sha(self.path))
    def test_default_stays_a367(self):
        self.assertIsNone(w.verify_memory_revision(None, self.boot))
        p = w.read(w.PREREG)
        m = w.memory_admission(p, None, 'MemAvailable: 119999999 kB')
        self.assertEqual(m['minimum_mem_available_bytes'], 120000000 * 1024)
        self.assertFalse(m['memory_floor_met'])
    def test_memory_boundary_and_insufficient_capacity(self):
        r = self.verify()
        for kib, passed in [(self.floor-1, False), (self.floor, True), (self.floor+1, True), (116384560, False)]:
            with self.subTest(kib=kib):
                self.assertEqual(w.memory_admission(w.read(w.PREREG), r,
                    f'MemAvailable: {kib} kB')['memory_floor_met'], passed)
    def test_unapproved_and_wrong_owner(self):
        for key, value in [('approved', False), ('approved', 'true'), ('approved', 1), ('approved_by', 'agent')]:
            with self.subTest(key=key, value=value):
                old = self.receipt[key]; self.receipt[key] = value
                with self.assertRaisesRegex(ValueError, 'approval'): self.verify()
                self.receipt[key] = old
    def test_missing_each_field(self):
        for key in list(self.receipt):
            with self.subTest(key=key):
                value = self.receipt.pop(key)
                with self.assertRaisesRegex(ValueError, 'fields'): self.verify()
                self.receipt[key] = value
    def test_extra_field(self):
        self.receipt['force'] = True
        with self.assertRaisesRegex(ValueError, 'fields'): self.verify()
    def test_wrong_schema(self):
        self.receipt['schema'] = 'unrelated'
        with self.assertRaisesRegex(ValueError, 'approval'): self.verify()
    def test_stale_hash(self):
        self.receipt['revision_document_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'hash'): self.verify()
    def test_wrong_host_or_boot(self):
        for key in ('host', 'boot_id'):
            old = self.receipt[key]; self.receipt[key] = 'other'
            with self.assertRaisesRegex(ValueError, 'host/boot'): self.verify()
            self.receipt[key] = old
    def test_arbitrary_or_mistyped_floor(self):
        for value in (True, False, 0, -1, '133542784', 133542784.0, 110000000, 133542785):
            with self.subTest(value=value):
                self.receipt['minimum_mem_available_kib'] = value
                with self.assertRaisesRegex(ValueError, 'floor'): self.verify()
    def test_approval_text_must_bind_floor_and_hash(self):
        for text in ('', 'approved', 'PENDING OWNER APPROVAL', w.approval_text(110000000, self.digest)):
            self.receipt['owner_approval_text'] = text
            with self.assertRaisesRegex(ValueError, 'approval text'): self.verify()
    def test_malformed_missing_or_duplicate_receipt(self):
        with self.assertRaises(FileNotFoundError): w.verify_memory_revision(self.path, self.boot)
        for text in ('{', 'null', '[]', '{"approved":true,"approved":false}'):
            self.path.write_text(text)
            with self.assertRaises((ValueError, TypeError)):
                w.verify_memory_revision(self.path, self.boot)
    def test_document_tampering(self):
        doc = self.root / 'revision.md'
        doc.write_bytes(w.REVISION_DOC.read_bytes() + b'changed')
        with patch.object(w, 'REVISION_DOC', doc):
            with self.assertRaisesRegex(ValueError, 'hash'): self.verify()
    def test_ambiguous_document_refused(self):
        doc = self.root / 'revision.md'
        doc.write_text('proposed_minimum_mem_available_kib: 133542784\n' * 2)
        self.receipt['revision_document_sha256'] = w.sha(doc)
        with patch.object(w, 'REVISION_DOC', doc):
            with self.assertRaisesRegex(ValueError, 'one floor'): self.verify()
    def test_pending_template_refused(self):
        with self.assertRaisesRegex(ValueError, 'approval'):
            w.verify_memory_revision(w.HERE / 'admission-revision.pending.json', self.boot)
    def test_identity_keeps_approval_and_delta(self):
        r = self.verify()
        self.path.write_text(self.path.read_text() + '  \n')
        r = w.verify_memory_revision(self.path, self.boot)
        paths = {k:Path(v) for k,v in w.read(w.PREREG)['defaults'].items()}
        args = types.SimpleNamespace(owner_window=self.path, health_receipt=self.path, payload_receipt=self.path)
        audit = {'versions': {}, 'memory_admission': w.memory_admission(w.read(w.PREREG), r,
                 f'MemAvailable: {self.floor} kB')}
        w.write(self.root/'environment.json', audit)
        w.make_identity(self.root, args, paths, {}, [], audit,
            {'host':'steve-b70s', 'boot_id':self.boot, 'firmware':'mock', 'pci_ids':[]},
            {'kernel':'mock'}, r)
        identity = w.read(self.root/'identity.json')
        self.assertEqual(identity['admission_revision'], r)
        self.assertEqual(identity['deltas'][-1]['to_bytes'], self.floor*1024)
        self.assertEqual(w.read(self.root/'admission-revision.json'), self.receipt)
        self.assertEqual(w.sha(self.root/'admission-revision.json'), r['receipt']['sha256'])
    def test_owner_pin_and_cli_must_agree(self):
        r = self.verify()
        owner = {'admission_revision_sha256': r['receipt']['sha256']}
        w.verify_revision_binding(owner, r)
        w.verify_revision_binding({}, None)
        for flag, revision in ((owner, None), ({}, r), ({'admission_revision_sha256': 'bad'}, r)):
            with self.assertRaisesRegex(ValueError, 'owner revision'):
                w.verify_revision_binding(flag, revision)
    def test_cli_plan_accepts_receipt_without_runtime_actions(self):
        self.receipt['boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        w.write(self.path, self.receipt)
        with patch.object(w.subprocess, 'Popen', side_effect=AssertionError('native launch')), \
             patch.object(w, 'verify_environment', side_effect=AssertionError('audit in plan')), \
             patch('builtins.print') as output:
            self.assertEqual(w.main(['--plan','--admission-revision',str(self.path),
                                   '--output',str(self.root/'unused')]), 0)
        import json
        plan = json.loads(output.call_args.args[0])
        self.assertFalse(plan['native_executed'])
        self.assertEqual(plan['memory_admission']['minimum_mem_available_bytes'], self.floor*1024)
        self.assertFalse((self.root/'unused').exists())


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='packet4-oracle-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for i in range(4): (self.root/f'rank-{i}').mkdir()
        self.ids = next(r['token_ids'] for r in w.read(w.ORACLE)['rows'] if r['prompt_id']==w.PROMPT_ID)[:64]
    def test_exact_prefix_not_full_pass(self):
        v=w.oracle_assert(self.ids, 0, 'length', self.root)
        self.assertTrue(v['passed']); self.assertFalse(v['full_oracle_equal'])
        self.assertFalse(v['realistic_final_gate']['passed'])
    def test_mismatch_void_all_ranks(self):
        self.ids[7] += 1
        with self.assertRaises(AssertionError): w.oracle_assert(self.ids,0,'length',self.root)
        for i in range(4): self.assertEqual(w.read(self.root/f'rank-{i}/VOID.json')['status'],'VOID')
    def test_early_eos_void(self):
        with self.assertRaises(AssertionError): w.oracle_assert(self.ids[:8],0,'stop',self.root)
    def test_cache_hit_void(self):
        with self.assertRaises(AssertionError): w.oracle_assert(self.ids,1,'length',self.root)
    def test_missing_ids_void(self):
        with self.assertRaises(AssertionError): w.oracle_assert(None,0,'length',self.root)
    def test_boolean_cache_not_zero(self):
        with self.assertRaises(AssertionError): w.oracle_assert(self.ids,False,'length',self.root)


class ControlTests(unittest.TestCase):
    def test_rank_budget_includes_receipts(self):
        p=w.read(w.PREREG)
        self.assertEqual(4*(p['rank_bytes']+p['rank_receipt_reserve_bytes']),p['shared_fixture_bytes'])
        self.assertGreaterEqual(p['rank_receipt_reserve_bytes'],1048576)
    def test_own_session_cannot_be_declared_gone(self):
        self.assertFalse(w.owned_session_gone(os.getsid(os.getpid())))
    def test_live_config_rejects_graph(self):
        with patch.dict(sys.modules):
            fake_vllm()
            sys.modules.pop('packet4_worker',None)
            from packet4_worker import live_execution
            cfg=types.SimpleNamespace(model_config=types.SimpleNamespace(enforce_eager=False),
                compilation_config=types.SimpleNamespace(mode=types.SimpleNamespace(name='NONE'),
                    cudagraph_mode=types.SimpleNamespace(name='FULL_DECODE_ONLY')),
                cache_config=types.SimpleNamespace(enable_prefix_caching=False))
            with self.assertRaisesRegex(ValueError,'eager/cache-free'):live_execution(cfg)
    def test_metadata_uses_cpu_scheduler_only(self):
        import torch
        import numpy as np
        with patch.dict(sys.modules):
            fake_vllm();sys.modules.pop('packet4_worker',None)
            from packet4_worker import ExtractionWorker
            worker=ExtractionWorker(rank=2,vllm_config=None)
            worker._packet4_in_target=True;worker._packet4_scheduled=2
            worker.model_runner=types.SimpleNamespace(input_batch=types.SimpleNamespace(
                num_reqs=1,num_computed_tokens_cpu=np.array([71])),query_pos=types.SimpleNamespace(np=np.array([0,1])))
            class DevicePositions:
                def numel(self):return 2
                def cpu(self):raise AssertionError('device read')
                def item(self):raise AssertionError('device scalar')
            b={'self':types.SimpleNamespace(layer_idx=0),'hidden_states':torch.zeros(2,4,8),
                'positions':DevicePositions()}
            self.assertEqual(worker._packet4_metadata(None,b)['positions'],[71,72])
            worker._packet4_in_target=False
            self.assertIsNone(worker._packet4_metadata(None,b))
            worker._packet4_in_target=True;worker._packet4_scheduled=3
            with self.assertRaisesRegex(ValueError,'padded'):worker._packet4_metadata(None,b)
    def test_watcher_fault_latches(self):
        with tempfile.TemporaryDirectory(prefix='packet4-watch-test-') as temp:
            root=Path(temp);boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            watch=w.Watch(root,'normal',boot)
            with patch.object(w,'journal',return_value='Fault response'):
                with self.assertRaisesRegex(ValueError,'new kernel fault'):watch.poll()
            self.assertTrue((root/'FAULT.json').exists())
    def test_watcher_unreadable_journal_fails(self):
        with tempfile.TemporaryDirectory(prefix='packet4-watch-test-') as temp:
            root=Path(temp);boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            watch=w.Watch(root,'normal',boot)
            with patch.object(w,'journal',side_effect=ValueError('journal unavailable')):watch.run()
            self.assertIn('unavailable',watch.failed);self.assertTrue((root/'STOP.json').exists())
    def test_real_seals(self): self.assertEqual(w.verify_repo()['patch_seal_members'],75)
    def test_tampered_seal(self):
        p=copy.deepcopy(w.read(w.PREREG)); p['repo_pins'][next(iter(p['repo_pins']))]='0'*64
        with self.assertRaisesRegex(ValueError,'seal mismatch'): w.verify_repo(p)
    def test_missing_environment_refuses_without_import(self):
        p=w.read(w.PREREG)
        with self.assertRaises(FileNotFoundError):
            w.verify_environment({k:Path('/nonexistent-packet4') for k in p['defaults']},p)
    def test_audit_keeps_stage_pass_when_later_check_refuses(self):
        import json
        def fail(paths, prereg, audit):
            audit['kernel_stage_passed'] = True
            raise ValueError('full model verification receipt absent/changed')
        with patch.object(w, 'verify_repo', return_value=w.read(w.PREREG)), \
             patch.object(w, 'verify_environment', side_effect=fail), \
             patch('builtins.print') as output:
            self.assertEqual(w.main(['--audit', '--output', '/tmp/packet4-test-no-create']), 2)
        audit = json.loads(output.call_args.args[0])
        self.assertTrue(audit['kernel_stage_passed'])
        self.assertFalse(audit['passed'])
        self.assertIn('receipt', audit['error'])
    def test_command_identity(self):
        paths={k:Path(v) for k,v in w.read(w.PREREG)['defaults'].items()}
        cmd=w.build_command(paths)
        for flag,value in [('--tensor-parallel-size','4'),('--max-num-batched-tokens','64'),
            ('--worker-cls','packet4_worker.ExtractionWorker'),('--cpu-offload-gb','12.25')]:
            self.assertEqual(cmd[cmd.index(flag)+1],value)
        self.assertIn('--enforce-eager',cmd); self.assertNotIn('8188',cmd)
    def test_environment_no_ambient_knobs(self):
        paths={k:Path(v) for k,v in w.read(w.PREREG)['defaults'].items()}
        with patch.dict(os.environ, {'VLLM_XPU_ENABLE_XPU_GRAPH':'1','NEOReadDebugKeys':'1','LD_PRELOAD':'bad'}):
            env=w.build_environment(paths,Path('/tmp/packet4-plan'))
        self.assertEqual(env['VLLM_XPU_ENABLE_XPU_GRAPH'],'0')
        self.assertNotIn('NEOReadDebugKeys',env)
        self.assertNotEqual(env['LD_PRELOAD'],'bad')
        self.assertEqual(env['OMP_NUM_THREADS'],'2')
    def test_fault_patterns(self):
        for s in ['Fault response','Engine memory CAT error','engine reset','Timedout job','Xe device coredump has been created']:
            self.assertEqual(w.fault_lines(s),[s])
        self.assertFalse(w.fault_lines('Xe device coredump has been deleted'))
        self.assertFalse(w.fault_lines('network link changed'))
    def test_wait_never_escalates(self):
        class Proc:
            pid=123; count=0
            def is_alive(self): return self.count<3
            def join(self,_): self.count+=1
            def kill(self): raise AssertionError('hard kill')
            def terminate(self): raise AssertionError('terminate')
        with tempfile.TemporaryDirectory(prefix='packet4-stop-test-') as temp:
            with patch.dict(os.environ,PACKET4_WINDOW=temp), patch.object(sg.time,'monotonic',side_effect=[0,301,302,303]):
                sg.wait_only([Proc()])
            self.assertEqual(w.read(Path(temp)/f'shutdown-wait-{os.getpid()}.json')['status'],'MANUAL-RECOVERY')
    def test_one_sigint_per_pid(self):
        class Proc:
            pid=987; alive=True
            def is_alive(self): return self.alive
            def join(self,_): self.alive=False
        sg._sent.clear()
        with patch.dict(os.environ,PACKET4_WINDOW='/tmp/unused'),patch.object(os,'kill') as kill:
            proc=Proc(); sg.request_and_wait([proc]); sg.request_and_wait([proc])
            kill.assert_called_once_with(987,signal.SIGINT)
    def test_four_subprocess_ranks_supported_injection(self):
        with tempfile.TemporaryDirectory(prefix='packet4-workers-test-') as temp:
            root=Path(temp)
            ids=next(r['token_ids'] for r in w.read(w.ORACLE)['rows'] if r['prompt_id']==w.PROMPT_ID)[:64]
            w.oracle_assert(ids,0,'length',root)
            env=dict(os.environ,PACKET4_WINDOW=temp,PYTHONDONTWRITEBYTECODE='1',
                     PYTHONPATH=str(w.HERE)+':'+str(w.PREP))
            # Actual source dispatch body resolves subclass in four fresh interpreters.
            for rank in range(4):
                result=subprocess.run([sys.executable,'-B',__file__,'--mock-rank',str(rank)],env=env,
                                      capture_output=True,text=True,timeout=60)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(w.read(root/f'rank-{rank}/registered.json')['registration_count'],1)
                self.assertTrue(w.read(root/f'rank-{rank}/teardown.json')['passed'])
                fixtures=list((root/f'rank-{rank}').glob('fixture-*.json'))
                self.assertEqual(len(fixtures),1)
                self.assertTrue(w.read(fixtures[0])['diagnostic']['mock'])


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--mock-rank':
        subprocess_rank(Path(os.environ['PACKET4_WINDOW']),int(sys.argv[2]))
    else:
        unittest.main()
