"""CPU-only lifecycle tests: every process, device and service action is mocked."""
from contextlib import ExitStack, contextmanager
import json
import errno
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import sparse_v1_host_runner as runner


def profile():
    return {'rung': {'tp': 2, 'mem': .95, 'max_model_len': 262144, 'batched': 832,
        'seqs': 1, 'mtp': 5, 'draft_int4': True, 'fa_verify_rows': True,
        'prefix_cache': 'off', 'warmup': False, 'image': runner.IMAGE, 'shortlist': '/pinned/list',
        'overlay': [], 'extra_env': [], 'env': [], 'serve_arg': []},
        'overlay_sha256': {'a': 'fixed'}, 'reference_sha256': 'fixed', 'guard_sha256': 'fixed'}


def strict_result():
    return {'schema': 'neural.download.strict-attempt-output-comparison.v1',
        'comparison': {'exact_prompts': 12, 'total_prompts': 12, 'complete_token_arrays_exact': True},
        'qualification': {'all_workload_and_canary_gates_passed': True, 'strict_pair_qualified': True}}


def planned():
    rows=[]
    for count,arm in ((8,'archive'),(8,'quoted'),(128,'quoted'),(128,'archive')):
        case=f'sparse-n{count}-seed83'; folder=f'{case}-{arm}'
        rows.append({'case_id':case,'counter_count':count,'arm':arm,
            'task_sha256':runner.hashlib.sha256(case.encode()).hexdigest(),'source_sha256':'1'*64,
            'adjudication_sha256':None,'task_path':case+'-task.json','document_path':case+'-document.json',
            'result_path':folder+'/result.json','native_result_path':folder+'/native/result.json',
            'generated_provenance':{'kind':'programmatically-generated','counter_count':count,'generator_seed':83}})
    return rows


def packet_fixture():
    rows=planned(); tasks={r['case_id']:{'document_id':r['case_id'],'task_sha256':r['task_sha256'],
        'source_sha256':r['source_sha256'],'generated_provenance':r['generated_provenance'],
        'questions':[{}]*24} for r in rows}
    return {'plan':{'schema':'sparse-state-plan.v1','protocol':runner.SPARSE_PROTOCOL,'trials':rows,
        'expected_trials':4,'answer_generation':dict(runner.ANSWER_GENERATION),
        'ingestion_generation':dict(runner.INGESTION_GENERATION),**runner.NATIVE_LIMITS},
        'tasks':tasks,'budget':{'schema':'sparse-state-budget-receipt.v1',
            'measurement_kind':'cpu-oracle-wiring-budget-check',
            'all_reference_prompts_fit':True,'all_reference_emissions_fit':True}}


def diagnostic_files(directory, failed=0, identity=None, sources=None):
    directory.mkdir(parents=True, exist_ok=True); rows=[]
    for index,item in enumerate(planned()):
        status='failed' if index<failed else 'completed'
        result={'schema':'semantic-live-trial.v1','measurement_kind':'model','document_id':item['case_id'],
            **item,'status':status,'protocol':runner.NATIVE_PROTOCOL,'resumed':False,'calls':1,
            'server_identity':identity,'source_code_sha256':sources,'artifacts':{},
            'answer_generation':dict(runner.ANSWER_GENERATION),
            'ingestion_generation':dict(runner.INGESTION_GENERATION),**runner.NATIVE_LIMITS}
        native=directory/item['native_result_path'];native.parent.mkdir(parents=True,exist_ok=True)
        runner.atomic(native,result)
        outer={'schema':'sparse-state-trial.v1','protocol':runner.SPARSE_PROTOCOL,**item,
            'measurement_kind':'model','status':status,'native_sha256':runner.sha(native),
            'native_artifacts':{},'speed_gate_passed':False,'holdout_admitted':False}
        runner.atomic(directory/item['result_path'],outer)
        rows.append({**item,'status':status})
    summary={'schema':'sparse-state-summary.v1','measurement_kind':'model','protocol':runner.SPARSE_PROTOCOL,
        'status':'completed','infrastructure_abort':False,'speed_gate_passed':False,'holdout_admitted':False,
        'trials':rows,'completed_trials':4-failed,'failed_trials':failed,'expected_trials':4,'observed_trials':4,
        'server_identity':identity,'engine_source_sha256':sources}
    runner.atomic(directory/'summary.json',summary);return summary


class DiagnosticCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.out=Path(self.temp.name)

    def test_complete_four_accepts_recorded_model_failures(self):
        for count in (0,2,4):
            diagnostic_files(self.out,count)
            self.assertEqual(runner.verify_diagnostic(self.out,planned())['failed_trials'],count)

    def test_incomplete_duplicate_reordered_or_claimed_summary_refused(self):
        for mode in ('partial','duplicate','order','speed','infrastructure','null'):
            result=diagnostic_files(self.out)
            if mode=='partial':result['trials'].pop()
            elif mode=='duplicate':result['trials'][1]=result['trials'][0]
            elif mode=='order':result['trials'].reverse()
            elif mode=='speed':result['speed_gate_passed']=True
            elif mode=='infrastructure':result['infrastructure_abort']=True
            else:result['failed_trials']=None
            runner.atomic(self.out/'summary.json',result)
            with self.assertRaises(RuntimeError):runner.verify_diagnostic(self.out,planned())

    def test_native_identity_caps_noresume_and_outer_hash_enforced(self):
        for field,value in [('protocol','wrong'),('resumed',True),('max_answer_calls',32.0),
                            ('task_sha256','wrong'),('answer_generation',{}),('source_code_sha256',{})]:
            result=diagnostic_files(self.out,sources={'live.py':'hash'})
            row=result['trials'][0];path=self.out/row['native_result_path']
            native=json.loads(path.read_text());native[field]=value;runner.atomic(path,native)
            outerpath=self.out/row['result_path'];outer=json.loads(outerpath.read_text())
            outer['native_sha256']=runner.sha(path);runner.atomic(outerpath,outer)
            with self.assertRaises(RuntimeError):runner.verify_diagnostic(self.out,planned(),source_code_sha256={'live.py':'hash'})
        result=diagnostic_files(self.out);native=self.out/result['trials'][0]['native_result_path']
        native.write_text(native.read_text()+' ')
        with self.assertRaisesRegex(RuntimeError,'hash'):runner.verify_diagnostic(self.out,planned())

    def test_outer_protocol_generated_identity_and_path_enforced(self):
        for field,value in [('protocol','semantic-development-live-v1'),('generated_provenance',{}),
                            ('native_result_path','../escape.json')]:
            result=diagnostic_files(self.out);path=self.out/result['trials'][0]['result_path']
            outer=json.loads(path.read_text());outer[field]=value;runner.atomic(path,outer)
            with self.assertRaises(RuntimeError):runner.verify_diagnostic(self.out,planned())

    def test_cache_observations_are_audit_only(self):
        summary=diagnostic_files(self.out)
        for cached,knownzero in ((0,True),(2,False),(None,False)):
            for row in summary['trials']:
                path=(self.out/row['native_result_path']).parent/'calls.jsonl'
                path.write_text(json.dumps({'usage':{'prompt_tokens':10,'prompt_tokens_details':{'cached_tokens':cached}}})+'\n')
            result=runner.verify_diagnostic(self.out,planned())
            self.assertEqual(result['host_cache_audit']['all_trials_known_zero'],knownzero)
            self.assertFalse(result['speed_gate_passed'])

    def test_fixed_sparse_order_and_task_hash_binding(self):
        packet=packet_fixture();self.assertEqual(runner.expected_trials(packet),planned())
        packet['plan']['trials'].reverse()
        with self.assertRaises(RuntimeError):runner.expected_trials(packet)

    def test_cpu_budget_requires_strict_fit_and_native_caps(self):
        for bad in ('fit','caps','schema'):
            packet=packet_fixture()
            if bad=='fit':packet['budget']['all_reference_emissions_fit']=False
            elif bad=='caps':packet['plan']['max_answer_calls']=64
            else:packet['budget']['schema']='other'
            response=SimpleNamespace(returncode=0,stdout=json.dumps(packet))
            with patch.object(runner.subprocess,'run',return_value=response):
                with self.assertRaises(RuntimeError):runner.validate_sparse_packet(self.out)
        with patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(packet_fixture()))):
            self.assertEqual(runner.validate_sparse_packet(self.out),packet_fixture())

    def test_dependencies_pin_local_tokenizer_and_interpreter(self):
        tokenizer=self.out/'tokenizer.json';tokenizer.write_text('{}')
        interpreter=self.out/'python';interpreter.write_text('cpu interpreter fixture')
        runner.atomic(self.out/'budget-receipt.json',{'tokenizer_path':str(tokenizer),
                      'tokenizer_python':str(interpreter)})
        with patch.object(runner,'sha',return_value='digest'):
            hashes=runner.dependencies(self.out/'launch.json',{'rung':{'overlay':[]}},self.out)
        self.assertIn(str(tokenizer),hashes);self.assertIn(str(interpreter),hashes)


class PureTests(unittest.TestCase):
    def test_strict_requires_all_qualification_flags(self):
        self.assertTrue(runner.strict_passed(strict_result()))
        for section, key in [('comparison', 'complete_token_arrays_exact'),
                             ('qualification', 'all_workload_and_canary_gates_passed'),
                             ('qualification', 'strict_pair_qualified')]:
            result = strict_result(); result[section][key] = False
            self.assertFalse(runner.strict_passed(result))
        result = strict_result(); result['schema'] = 'other'
        self.assertFalse(runner.strict_passed(result))

    def test_profile_is_immutable_image_and_single_sequence(self):
        self.assertIn(runner.IMAGE, runner.profile_args(profile()))
        for key, value in [('image', 'mutable:latest'), ('seqs', 2), ('mtp', 1)]:
            altered = profile(); altered['rung'][key] = value
            with self.assertRaises(ValueError): runner.profile_args(altered)

    def test_pid_reuse_and_zombie_are_not_protected_owner(self):
        original = {'start_ticks': '123'}
        self.assertTrue(runner.same_process(original, {'start_ticks': '123', 'state': 'S'}))
        self.assertFalse(runner.same_process(original, {'start_ticks': '124', 'state': 'S'}))
        self.assertFalse(runner.same_process(original, {'start_ticks': '123', 'state': 'Z'}))
        self.assertFalse(runner.same_process(original, None))

    def test_process_identity_handles_spaces_in_comm(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); proc = root / '5'; proc.mkdir()
            (proc / 'stat').write_text('5 (a process) S ' + ' '.join(['0'] * 18 + ['789', '0']))
            (proc / 'cmdline').write_bytes(b'bash\0supervise.sh\0')
            self.assertEqual(runner.process_identity(5, root)['start_ticks'], '789')

    def test_added_runtime_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            launch = Path(directory) / 'launch.json'; launch.write_text('{}')
            config = {'hostname': runner.socket.gethostname(), 'packet': '/fake-packet', 'previous_revision': {'artifacts': {}},
                'protected_launch': str(launch), 'dependency_sha256': {str(launch): runner.sha(launch)}}
            with patch.object(runner, 'dependencies', return_value={**config['dependency_sha256'], 'added.py': 'hash'}):
                with self.assertRaisesRegex(RuntimeError, 'inventory'): runner.verify_dependencies(config)

    def test_health_env_cannot_skip_collective_or_assertions(self):
        env = runner.health_env()
        self.assertEqual(env['XCCL_NPROC'], '2')
        self.assertEqual(env['XPU_HEALTH_SKIP_XCCL'], '0')
        self.assertEqual(env['PHYSICAL_DEVICES'], '0,1')
        self.assertEqual(env['PYTHONOPTIMIZE'], '')

    def test_release_rejects_busy_prior_units(self):
        with patch.object(runner, 'conflicting_processes', return_value=[]), \
             patch.object(runner, 'read_command', return_value=SimpleNamespace(stdout='ctx-semantic-v1.service loaded active running old')):
            self.assertIn('prior protected', runner.release_reason({}))

    def test_release_allows_stopped_prior_quality_failure(self):
        for state in ('failed failed', 'inactive dead'):
            with patch.object(runner, 'conflicting_processes', return_value=[]), \
                 patch.object(runner, 'read_command', return_value=SimpleNamespace(
                     stdout='ctx-semantic-v1.service loaded ' + state)) as inspect:
                self.assertIsNone(runner.release_reason({}))
                self.assertIn('ctx-semantic-v1.service', inspect.call_args.args[0])



class ColdProfileTests(unittest.TestCase):
    def qualified(self):
        launch = profile(); launch['rung']['prefix_cache'] = 'align'
        launch['rung']['warmup'] = True
        launch['rung']['serve_arg'] = ['--reasoning-parser=qwen3', '--prefix-cache-retention-interval=13312']
        return launch

    def test_derive_cold_profile_only_changes_declared_settings(self):
        qualified = self.qualified(); before = json.dumps(qualified, sort_keys=True)
        cold = runner.derive_cold_launch(qualified)
        self.assertEqual(json.dumps(qualified, sort_keys=True), before)
        expected = self.qualified(); expected['rung'].update(prefix_cache='off', warmup=False)
        expected['rung']['serve_arg'].remove('--prefix-cache-retention-interval=13312')
        self.assertEqual(cold, expected)
        self.assertIn('off', runner.profile_args(cold))

    def test_emission_rejects_enable_duplicate_missing_and_mode_overrides(self):
        for flags in ([], ['--no-enable-prefix-caching', '--no-enable-prefix-caching'],
                      ['--no-enable-prefix-caching', '--enable-prefix-caching'],
                      ['--no-enable-prefix-caching', '--enable-prefix-caching=false'],
                      ['--no-enable-prefix-caching=False'],
                      ['--no-enable-prefix-caching', '--mamba-cache-mode', 'align'],
                      ['--no-enable-prefix-caching', '--mamba-cache-mode=align'],
                      ['--no-enable-prefix-caching', '--prefix-cache-retention-interval=13312']):
            cold = runner.derive_cold_launch(self.qualified())
            cold['argv'] = ['docker', 'run', runner.IMAGE, *flags]
            with self.assertRaises(RuntimeError): runner.verify_cold_emission(cold)
        cold['argv'] = ['docker', 'run', runner.IMAGE, '--no-enable-prefix-caching']
        runner.verify_cold_emission(cold)
        cold['rung']['warmup'] = True
        with self.assertRaisesRegex(RuntimeError, 'warmup'): runner.verify_cold_emission(cold)

    def test_derive_refuses_other_cache_overrides(self):
        for override in ('--enable-prefix-caching', '--mamba-cache-mode=align',
                         '--prefix-cache-retention-interval=832'):
            qualified = self.qualified(); qualified['rung']['serve_arg'].append(override)
            with self.assertRaises(ValueError): runner.derive_cold_launch(qualified)

    def test_actual_qualified_launcher_build_emits_cold_flags_cpu_only(self):
        spec = runner.importlib.util.spec_from_file_location('cold_launcher_test', runner.LAUNCHER)
        module = runner.importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        cold = runner.derive_cold_launch(self.qualified())
        args = SimpleNamespace(**cold['rung'])
        for key, value in dict(draft_fp16_shortlist='', spec_config_json='', eager=False,
                               cpu_embed=False, layer_hash=0, gdn_head_groups=0, fa_trace=False,
                               mount_file=[], mount_dir=[], port=18196).items():
            setattr(args, key, value)
        reference_command = ['--tensor-parallel-size', '2', '--gpu-memory-utilization', '.95',
            '--max-model-len', '262144', '--max-num-batched-tokens', '832', '--max-num-seqs', '1',
            '--speculative-config', '{}', '--no-enable-prefix-caching']
        with patch.object(module, 'reference', return_value=({}, reference_command)):
            cold['argv'] = module.build(args, 'cpu-test-only', Path('/unused'), [])
        runner.verify_cold_emission(cold)
        self.assertNotIn('--enable-prefix-caching', cold['argv'])
        self.assertNotIn('--mamba-cache-mode', cold['argv'])

    def test_owned_server_does_not_send_warmup_before_identity_check(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner.subprocess, 'Popen') as popen:
            server = runner.OwnedServer(Path(directory), {'port': 18196, 'server_args': []})
            try: self.assertNotIn('--warmup', popen.call_args.args[0])
            finally: server.handle.close()


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.out = Path(self.directory.name)
        identity = profile(); identity['argv'] = ['docker', 'run', runner.IMAGE, '--no-enable-prefix-caching']
        self.config = {'schema': 'sparse-host-queue.v1', 'protocol': 'context-sparse-live-v1', 'packet': '/fake-packet', 'server_args': runner.profile_args(identity), 'port': 18196,
            'expected_trials': planned(),
            'cache_policy': dict(runner.CACHE_POLICY),
            'model': 'test-model', 'max_wait_seconds': 1,
            'effective_profile': runner.effective_profile(identity),
            'expected_launch_identity': {k: identity[k] for k in ('overlay_sha256', 'reference_sha256', 'guard_sha256')}}
        runner.atomic(self.out / 'queue.json', self.config)
        runner.atomic(self.out / 'status.json', {'phase': 'prepared'})
        self.held = set(); self.calls = []; self.stop_count = 0; self.starts = 0
        self.fail_command = None; self.fail_stop = False; self.fail_ready = False
        self.bad_emission = False
        self.strict_qualified = True; self.failed_trials = 0
        self.fail_cleanup_lock = False; self.cleanup_lock_failed = False
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        def patched(name, value): self.stack.enter_context(patch.object(runner, name, value))
        @contextmanager
        def lock(path):
            self.assertNotIn(path, self.held, 'nested flock would conflict')
            if (self.fail_cleanup_lock and path == runner.MODEL_LOCK and self.starts
                    and 'diagnostic' in self.calls and not self.cleanup_lock_failed):
                self.cleanup_lock_failed = True
                raise BlockingIOError('model lock stolen')
            self.held.add(path)
            try: yield
            finally: self.held.remove(path)
        patched('file_lock', lock)
        patched('verify_dependencies', lambda config: None)
        patched('expected_trials', lambda *args: planned())
        patched('validate_sparse_packet', lambda *args: packet_fixture())
        patched('fault_check', lambda config, out: None)
        patched('release_reason', lambda config: None)
        def available(*args): self.assertIn(runner.STAGE_LOCK, self.held)
        patched('load_helper', lambda: SimpleNamespace(check_available=available))
        def resource(*args):
            self.assertIn(runner.MODEL_LOCK, self.held); self.assertIn(runner.STAGE_LOCK, self.held)
        patched('resource_check', resource)
        testcase = self
        class Server:
            def __init__(self, out, config):
                testcase.starts += 1
                testcase.assertIn(runner.MODEL_LOCK, testcase.held)
                testcase.assertNotIn(runner.STAGE_LOCK, testcase.held)
                self.out = out / 'server'; self.out.mkdir()
                if testcase.bad_emission: identity['argv'].append('--enable-prefix-caching')
                runner.atomic(self.out / 'launch.json', identity)
            def wait_ready(self, out):
                if testcase.fail_ready: raise RuntimeError('startup failed')
            def stop(self):
                testcase.stop_count += 1
                if testcase.fail_stop: raise RuntimeError('STOP not confirmed')
                return {'stop_confirmed': True}
        patched('OwnedServer', Server)
        def command(args, name, out, config, **kwargs):
            self.calls.append(name)
            self.assertIn(runner.HOST_LOCK, self.held)
            if name.endswith('health'):
                self.assertIn(runner.STAGE_LOCK, self.held)
                self.assertIn(runner.MODEL_LOCK, self.held)
                self.assertEqual(kwargs['env'], runner.health_env())
            elif name.startswith('strict'):
                self.assertIn(runner.MODEL_LOCK, self.held)
            else:
                self.assertNotIn(runner.MODEL_LOCK, self.held)
            if name == self.fail_command: raise RuntimeError(name + ' failure')
            if name == 'strict-compare':
                result = strict_result(); result['qualification']['strict_pair_qualified'] = self.strict_qualified
                runner.atomic(out / 'strict-comparison.json', result)
            if name == 'diagnostic':
                self.assertIn(runner.SPARSE / 'runner.py', args)
                self.assertIn('--packet', args)
                self.assertIn('--identity', args)
                self.assertNotIn('--stage', args)
                self.assertNotIn('--calibration', args)
                diagnostic_files(out / 'diagnostic', self.failed_trials,
                    identity={'endpoint': 'http://127.0.0.1:18196/v1', 'model': config['model'],
                              'launch_sha256': runner.sha(out / 'server/launch.json')},
                    sources={p.name: runner.sha(p) for p in runner.SEMANTIC.glob('*.py')
                             if not p.name.startswith('test_')})
        patched('monitored_command', command)
        patched('STOP_REQUESTED', False)
        patched('status', self.write_status)

    def write_status(self, out, phase, **details):
        runner.atomic(out / 'status.json', {'phase': phase, **details})

    def phase(self): return json.loads((self.out / 'status.json').read_text())['phase']

    def test_success_lock_order_and_single_server(self):
        runner.execute(self.out)
        self.assertEqual(self.starts, 1); self.assertEqual(self.stop_count, 1)
        self.assertEqual(self.phase(), 'completed')
        self.assertEqual(self.calls, ['preflight-health', 'strict', 'strict-compare',
            'diagnostic', 'postflight-health'])
        self.assertTrue((self.out / 'cards-released.json').exists())

    def test_recorded_model_failures_complete_without_additional_stages(self):
        self.failed_trials = 2
        runner.execute(self.out)
        self.assertEqual(self.phase(), 'completed')
        self.assertEqual(self.calls, ['preflight-health', 'strict', 'strict-compare',
                                     'diagnostic', 'postflight-health'])
        status = json.loads((self.out / 'status.json').read_text())
        self.assertEqual(status['failed_trials'], 2)
        self.assertFalse(status['speed_gate_passed']); self.assertFalse(status['holdout_admitted'])
        self.assertEqual(self.stop_count, 1)

    def test_diagnostic_infrastructure_failure_preserves_stop_receipt(self):
        self.fail_command = 'diagnostic'
        with self.assertRaisesRegex(RuntimeError, 'diagnostic'): runner.execute(self.out)
        self.assertEqual(self.phase(), 'failed'); self.assertEqual(self.stop_count, 1)
        self.assertEqual(self.calls.count('diagnostic'), 1); self.assertNotIn('postflight-health', self.calls)
        self.assertTrue((self.out / 'server-stop.json').exists())
        self.assertTrue((self.out / 'cards-released.json').exists())

    def test_startup_failure_stops_once(self):
        self.fail_ready = True
        with self.assertRaisesRegex(RuntimeError, 'startup failed'): runner.execute(self.out)
        self.assertEqual(self.stop_count, 1); self.assertNotIn('strict', self.calls)

    def test_bad_actual_cache_argv_stops_before_any_model_request(self):
        self.bad_emission = True
        with self.assertRaisesRegex(RuntimeError, 'cache enabling'): runner.execute(self.out)
        self.assertEqual(self.calls, ['preflight-health'])
        self.assertEqual(self.stop_count, 1)

    def test_failed_strict_gate_does_not_reach_diagnostic(self):
        self.strict_qualified = False
        with self.assertRaisesRegex(RuntimeError, 'strict standing-reference'): runner.execute(self.out)
        self.assertNotIn('diagnostic', self.calls); self.assertEqual(self.stop_count, 1)

    def test_stop_failure_never_retries_stop_or_health(self):
        self.fail_stop = True
        with self.assertRaisesRegex(RuntimeError, 'STOP not confirmed'): runner.execute(self.out)
        self.assertEqual(self.stop_count, 1); self.assertEqual(self.phase(), 'cleanup-failed')
        self.assertNotIn('postflight-health', self.calls)

    def test_cleanup_lock_conflict_still_requests_one_stop(self):
        self.fail_cleanup_lock = True
        with self.assertRaisesRegex(BlockingIOError, 'model lock stolen'): runner.execute(self.out)
        self.assertEqual(self.stop_count, 1); self.assertEqual(self.phase(), 'cleanup-failed')
        self.assertTrue((self.out / 'server-stop.json').exists())

    def test_postflight_failure_is_terminal_failed(self):
        self.fail_command = 'postflight-health'
        with self.assertRaisesRegex(RuntimeError, 'postflight-health'): runner.execute(self.out)
        self.assertEqual(self.phase(), 'failed'); self.assertEqual(self.stop_count, 1)

    def test_drift_prevents_any_launch(self):
        with patch.object(runner, 'verify_dependencies', side_effect=RuntimeError('source drift')):
            with self.assertRaisesRegex(RuntimeError, 'source drift'): runner.execute(self.out)
        self.assertEqual(self.starts, 0); self.assertEqual(self.calls, [])
        self.assertEqual(self.phase(), 'failed')

    def test_marker_rechecked_after_coordinator_lock(self):
        @contextmanager
        def racing_lock(path):
            self.held.add(path)
            if path == runner.HOST_LOCK: runner.atomic(self.out / 'execution-started.json', {'other': True})
            try: yield
            finally: self.held.remove(path)
        with patch.object(runner, 'file_lock', racing_lock):
            with self.assertRaisesRegex(RuntimeError, 'already executed'): runner.execute(self.out)
        self.assertEqual(self.starts, 0)


class PortHandoffTests(unittest.TestCase):
    def test_transient_port_teardown_waits_without_device_actions(self):
        helper = SimpleNamespace(check_available=Mock(side_effect=[
            OSError(errno.EADDRINUSE, 'teardown'), None]))
        with patch.object(runner.time, 'sleep') as sleep, patch.object(runner, 'fault_check') as faults:
            runner.wait_available({'port': 18196}, Path('/unused'), helper)
        self.assertEqual(helper.check_available.call_count, 2)
        sleep.assert_called_once_with(3)
        faults.assert_called_once()

    def test_persistent_port_and_unrelated_errors_fail_closed(self):
        helper = SimpleNamespace(check_available=Mock(side_effect=OSError(errno.EADDRINUSE, 'occupied')))
        with patch.object(runner.time, 'monotonic', side_effect=[0, 181]):
            with self.assertRaisesRegex(RuntimeError, 'did not release'):
                runner.wait_available({'port': 18196}, Path('/unused'), helper)
        helper.check_available.side_effect = OSError(errno.EACCES, 'not allowed')
        with self.assertRaises(OSError):
            runner.wait_available({'port': 18196}, Path('/unused'), helper)



class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.prior = self.root / 'previous'; self.prior.mkdir()
        (self.prior / 'server').mkdir()
        self.boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.packet=self.root/'old-packet';self.packet.mkdir()
        for name in ('documents.json','adjudicated.json'):(self.packet/name).write_text('{}')
        self.audit=self.root/'independent-audit.json'
        self.addCleanup(patch.stopall)
        patch.object(runner,'SEMANTIC_PACKET',self.packet).start()
        patch.object(runner,'SEMANTIC_AUDIT',self.audit).start()
        runner.atomic(self.audit,{'schema':'semantic-native-audit.v1','output':str(self.prior),
            'measurement_kind':'model','infrastructure_abort':False,'planned_trials':36,
            'completed_trials':30,'failed_trials':6,'unstarted_trials':0,
            'documents_sha256':runner.sha(self.packet/'documents.json'),
            'adjudication_sha256':runner.sha(self.packet/'adjudicated.json')})
        runner.atomic(self.prior / 'queue.json', {'boot_id': self.boot, 'prepared_at': '2026-10-07T00:00:00Z',
            'dependency_sha256':{str(self.packet/name):runner.sha(self.packet/name) for name in ('documents.json','adjudicated.json')}})
        runner.atomic(self.prior / 'status.json', {'phase': 'completed'})
        (self.prior/'diagnostic').mkdir()
        runner.atomic(self.prior/'diagnostic/summary.json',{'schema':'semantic-live-summary.v1','status':'completed',
            'infrastructure_abort':False,'expected_trials':36,'observed_trials':36})
        runner.atomic(self.prior/'diagnostic-host-audit.json',{})
        (self.prior / 'lifecycle.jsonl').write_text('preserved evidence\n')
        state = {'boot_id': self.boot, 'stop_confirmed': True, 'owner_pid': 4,
                 'container_id': 'old', 'image_id': runner.IMAGE}
        runner.atomic(self.prior / 'server-stop.json', state)
        runner.atomic(self.prior / 'server/state.json', state)
        qualified = profile(); qualified['rung']['prefix_cache'] = 'align'
        qualified['rung']['serve_arg'] = ['--prefix-cache-retention-interval=13312']
        runner.atomic(self.prior / 'server/launch.json', qualified)
        runner.atomic(self.prior / 'cards-released.json', {'verified': True})

    def test_fresh_revision_prepare_is_passive_and_preserves_receipts(self):
        stack = ExitStack(); self.addCleanup(stack.close)
        for lock in ('HOST_LOCK', 'MODEL_LOCK', 'STAGE_LOCK'):
            stack.enter_context(patch.object(runner, lock, self.root / lock))
        stack.enter_context(patch.object(runner.socket, 'gethostname', return_value='steve-TURIND8-2L2T'))
        stack.enter_context(patch.object(runner, 'dependencies', return_value={'frozen': 'hash'}))
        stack.enter_context(patch.object(runner, 'expected_trials', return_value=planned()))
        stack.enter_context(patch.object(runner, 'validate_sparse_packet', return_value=packet_fixture()))
        stack.enter_context(patch.object(runner, 'release_reason', return_value=None))
        stack.enter_context(patch.object(runner, 'load_helper', return_value=SimpleNamespace(check_available=Mock())))
        stack.enter_context(patch.object(runner, 'resource_check'))
        stack.enter_context(patch.object(runner, 'fault_check'))
        launch = self.prior / 'server/launch.json'; out = self.root / 'new'
        with patch.object(runner, 'monitored_command') as commands, patch.object(runner, 'OwnedServer') as servers:
            (self.root/'budget-receipt.json').write_text('{}')
            result = runner.prepare(out, self.prior, launch, self.root)
            commands.assert_not_called(); servers.assert_not_called()
        self.assertEqual(result['schema'], 'sparse-host-queue.v1')
        self.assertEqual(result['protocol'], 'context-sparse-live-v1')
        self.assertEqual(result['fault_baseline_at'], '2026-10-07T00:00:00Z')
        self.assertNotIn('previous_prelaunch_failure', result)
        for path, digest in result['previous_revision']['artifacts'].items():
            self.assertEqual(runner.sha(path), digest)
        self.assertEqual(json.loads((out / 'status.json').read_text())['phase'], 'prepared')

    def test_previous_boot_or_missing_release_refused(self):
        runner.previous_receipts(self.prior)
        runner.atomic(self.prior / 'cards-released.json', {'verified': False})
        with self.assertRaisesRegex(RuntimeError, 'consistent stop'): runner.previous_receipts(self.prior)
        runner.atomic(self.prior / 'cards-released.json', {'verified': True})
        state = json.loads((self.prior / 'server-stop.json').read_text()); state['boot_id'] = 'other'
        runner.atomic(self.prior / 'server-stop.json', state)
        with self.assertRaisesRegex(RuntimeError, 'different boot'): runner.previous_receipts(self.prior)

    def test_previous_semantic_full_audit_required_without_accuracy_gate(self):
        _,frozen=runner.previous_receipts(self.prior)
        self.assertIn(str(self.audit),frozen)
        original=json.loads(self.audit.read_text())
        for key,value in [('unstarted_trials',1),('measurement_kind','stub'),
                          ('infrastructure_abort',True),('completed_trials',None),
                          ('documents_sha256','changed'),('output',str(self.root/'other'))]:
            runner.atomic(self.audit,{**original,key:value})
            with self.assertRaises(RuntimeError):runner.previous_receipts(self.prior)
        runner.atomic(self.audit,original)
        runner.atomic(self.prior/'status.json',{'phase':'running'})
        with self.assertRaisesRegex(RuntimeError,'has not completed'):runner.previous_receipts(self.prior)

    def test_failed_status_links_existing_results(self):
        out = self.root / 'results'; (out / 'diagnostic').mkdir(parents=True)
        diagnostic_files(out / 'diagnostic', 2)
        runner.status(out, 'failed', error='diagnostic infrastructure failure')
        result = json.loads((out / 'status.json').read_text())
        self.assertEqual(result['available_results']['diagnostic'], str(out / 'diagnostic/summary.json'))


if __name__ == '__main__': unittest.main()
