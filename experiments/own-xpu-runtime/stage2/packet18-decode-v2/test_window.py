#!/usr/bin/env python3
"""CPU-only protocol tests. Fake children never launch a device binary."""
import importlib.util
import io
import json
from pathlib import Path
import signal
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('packet18_window', HERE / 'window.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


class Clock:
    def __init__(self): self.t = 0
    def now(self): return self.t
    def sleep(self, amount): self.t += amount


class Child:
    def __init__(self, clock, end=None, stop=True):
        self.clock, self.end, self.stop = clock, end, stop
        self.returncode = None
        self.signals = []
    def poll(self):
        if self.end is not None and self.clock.t >= self.end:
            self.returncode = 0
        return self.returncode
    def send_signal(self, sig):
        self.signals.append(sig)
        if self.stop: self.returncode = -sig


class Windows(unittest.TestCase):
    def setUp(self):
        (HERE / 'build').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='window-tests-', dir=HERE / 'build')
        self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    def fake_run(self, count=8, steps=8, cards=1):
        run = self.root / 'run'
        for step in range(1, steps + 1):
            (run / f'step{step}').mkdir(parents=True, exist_ok=True)
            for layer in range(48):
                (run / f'step{step}/layer-{layer:02}.bf16').write_bytes(bytes([layer]) * 20480)
        receipt = dict(passed=True, tokens=[332] * count, owner_cards=cards,
                       schema='own-runtime.iq3.packet18.run.v1', device_executed=True,
                       arithmetic=w.AUTHORITY, context=256 if count>1 else 128,
                       nongemv='parallel', gemv='frozen', memory_mode='resident' if cards==2 else 'layer-streaming',
                       decode_tokens=count-1, decode_wall_ms=1000, decode_tok_s=count-1,
                       teardown=[dict(safe_to_exit=True, live_bytes=0, in_flight=0)])
        self.write(run / 'receipt.json', receipt)
        fields = ('wall_ms', 'gemv_device_ms', 'non_gemv_device_ms', 'transfer_wall_ms', 'kernel_submissions', 'host_waits')
        (run / 'timings.jsonl').write_text('\n'.join(json.dumps(dict(dict.fromkeys(fields, 1), kind='generated_token', generated_index=i+1, token_id=332)) for i in range(count)))
        return w.fixtures(run, steps)
    def watch(self, child, clock, seconds=1, journal=lambda _: ('', 'cursor')):
        requested, latched = [], []
        record = w.supervise(child, seconds, 'cursor', io.StringIO(), latched.append, lambda: None,
                             requested, journal=journal, now=clock.now, sleep=clock.sleep, drain_seconds=2)
        return record, requested, latched
    def test_watchdog_bounds_and_defaults(self):
        self.assertEqual(w.watchdog_seconds('W0'), 600)
        for value in (0, 30, 299, 1801):
            with self.assertRaisesRegex(ValueError, 'watchdog'):
                w.watchdog_seconds('W0', value)
        for value in (300, 600, 1800):
            self.assertEqual(w.watchdog_seconds('W0', value), value)
        for name in ('W1', 'W2', 'W3'):
            self.assertEqual(w.watchdog_seconds(name), 10800)
            with self.assertRaisesRegex(ValueError, 'watchdog'):
                w.watchdog_seconds(name, 7799)

    def test_slow_startup_and_expectation_do_not_signal(self):
        clock = Clock(); child = Child(clock, end=95)
        record, requested, latched = self.watch(child, clock, seconds=w.watchdog_seconds('W0'))
        self.assertFalse(child.signals or requested or latched)
        self.assertGreater(record['elapsed_seconds'], 30)

    def test_canary_timing_and_submission_budget(self):
        row = dict(schema='own-runtime.iq3.packet18.canary.v2', passed=True,
                   device_executed=True, owner_cards=2, round_trips=100,
                   kernels_per_card=1000, token_sequence=True, owned_device_bytes=1344,
                   wall_ms=200000, startup_jit_ms=150000, device_work_ms=100,
                   work_wall_ms=49900, teardown_ms=100, max_submission_ns=1000,
                   submission_budget_passed=True,
                   teardown=[dict(safe_to_exit=True, live_bytes=0, in_flight=0)])
        w.canary_receipt_gate(row)  # Total and work duration are never pass gates.
        for changes in ({'max_submission_ns':100000000}, {'submission_budget_passed':False},
                        {'startup_jit_ms':float('nan')}, {'device_work_ms':-1},
                        {'schema':'own-runtime.iq3.packet18.canary.v1'}):
            with self.assertRaises(ValueError): w.canary_receipt_gate(dict(row, **changes))

    def test_deadline_sends_one_sigterm(self):
        clock = Clock(); child = Child(clock)
        record, requested, latched = self.watch(child, clock)
        self.assertEqual(child.signals, [signal.SIGTERM])
        self.assertFalse(record['child_still_running'])
        self.assertIn('window deadline', requested)
        self.assertTrue(latched)
    def test_stuck_child_is_retained_with_bounded_drain(self):
        clock = Clock(); child = Child(clock, stop=False)
        record, _, latched = self.watch(child, clock)
        self.assertEqual(child.signals, [signal.SIGTERM])
        self.assertTrue(record['child_still_running'])
        self.assertLessEqual(clock.t, 3.25)
        self.assertTrue(latched)
    def test_fault_stops_once(self):
        clock = Clock(); child = Child(clock)
        record, requested, _ = self.watch(child, clock, journal=lambda _: ('xe Fault response\n', 'cursor'))
        self.assertEqual(child.signals, [signal.SIGTERM])
        self.assertIn('new GPU fault signature', requested)
    def test_journal_failure_stops(self):
        def broken(_): raise RuntimeError('denied')
        clock = Clock(); child = Child(clock)
        _, requested, _ = self.watch(child, clock, journal=broken)
        self.assertEqual(child.signals, [signal.SIGTERM])
        self.assertTrue(requested[0].startswith('kernel journal unavailable'))
    def test_success_no_signal(self):
        clock = Clock(); child = Child(clock, end=.5)
        record, requested, latched = self.watch(child, clock, seconds=2)
        self.assertEqual(child.signals, [])
        self.assertFalse(requested or latched)
        self.assertEqual(record['returncode'], 0)
    def test_exact_w1(self):
        hashes = self.fake_run()
        run, actual = w.compare_run(self.root, w.CONFIG['W1'], hashes, [332]*8)
        self.assertEqual(actual, hashes)
    def test_first_layer_mismatch_localized(self):
        hashes = self.fake_run()
        (self.root / 'run/step1/layer-12.bf16').write_bytes(b'x' * 20480)
        with self.assertRaisesRegex(ValueError, 'first differing layer fixture: step1/layer-12'):
            w.compare_run(self.root, w.CONFIG['W1'], hashes, [332]*8)
    def test_missing_fixture_refused(self):
        self.fake_run()
        (self.root / 'run/step1/layer-04.bf16').unlink()
        with self.assertRaisesRegex(ValueError, 'fixture missing'):
            w.fixtures(self.root / 'run', 1)
    def test_token_mismatch_localized(self):
        hashes = self.fake_run()
        with self.assertRaisesRegex(ValueError, 'generated token: 1'):
            w.compare_run(self.root, w.CONFIG['W1'], hashes, [333]*8)
    def test_unsafe_teardown_refused(self):
        hashes = self.fake_run()
        path = self.root / 'run/receipt.json'; r = w.read(path)
        r['teardown'][0]['in_flight'] = 1; self.write(path, r)
        with self.assertRaisesRegex(ValueError, 'unsafe teardown'):
            w.compare_run(self.root, w.CONFIG['W1'], hashes, [332]*8)
    def test_two_queue_owner_coverage(self):
        hashes = self.fake_run(64, 8, 2)
        run, _ = w.compare_run(self.root, w.CONFIG['W2'], hashes, [332]*64)
        self.assertTrue(w.safe_teardown(run, 2))
        del run['owner_cards']
        self.assertFalse(w.safe_teardown(run, 2))
    def test_timing_count_refused(self):
        hashes = self.fake_run()
        (self.root / 'run/timings.jsonl').write_text('')
        with self.assertRaisesRegex(ValueError, 'timing row coverage'):
            w.compare_run(self.root, w.CONFIG['W1'], hashes, [332]*8)
    def test_timing_index_refused(self):
        hashes = self.fake_run()
        path = self.root / 'run/timings.jsonl'; rows = [json.loads(line) for line in path.read_text().splitlines()]; row = rows[0]
        row['generated_index'] = 2; path.write_text('\n'.join(json.dumps(r) for r in rows))
        with self.assertRaisesRegex(ValueError, 'omitted/reordered'):
            w.compare_run(self.root, w.CONFIG['W1'], hashes, [332]*8)
    def test_wrong_decode_numerator_refused(self):
        hashes = self.fake_run(64, 8, 2)
        path = self.root / 'run/receipt.json'; row = w.read(path)
        row['decode_tokens'] = 64; self.write(path, row)
        with self.assertRaisesRegex(ValueError, 'numerator'):
            w.compare_run(self.root, w.CONFIG['W2'], hashes, [332]*64)
    def test_w1_gate_binds_boot_binary_and_input(self):
        hashes = self.fake_run()
        r = dict(schema='own-runtime.iq3.packet18.window.v1', window='W1', passed=True,
                 oracle_exact=True, boot_id='boot', binary_sha256='bin', input_sha256='input',
                 arithmetic=w.AUTHORITY, nongemv='parallel', gemv='frozen', layer_hashes=hashes,
                 tokens=[332]*8, native_receipt_sha256=w.sha(self.root / 'run/receipt.json'))
        path = self.root / 'window.json'; self.write(path, r)
        w.w1_gate(path, 'bin', 'input', 'boot')
        for args in [('wrong', 'input', 'boot'), ('bin', 'wrong', 'boot'), ('bin', 'input', 'wrong')]:
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                w.w1_gate(path, *args)
    def test_w1_gate_requires_receipt(self):
        with self.assertRaisesRegex(ValueError, 'require --w1'):
            w.w1_gate(None, '', '', '')
    def test_repeat_different_dispatch_refused(self):
        hashes = self.fake_run()
        r = dict(window='W1', passed=True, layer_hashes=hashes, gemv='frozen')
        path = self.root / 'window.json'; self.write(path, r)
        with self.assertRaisesRegex(ValueError, 'repeat anchor'):
            w.repeat_gate(path, dict(r, gemv='r5'))
    def test_packet2_fault_signatures(self):
        for text in ('Fault response', 'CAT error', 'engine reset', 'device coredump', 'timed out job'):
            self.assertIsNotNone(w.p2.FAULT.search(text))
        self.assertIsNone(w.p2.FAULT.search('ordinary change'))
    def test_cpu_receipt_binding_and_coverage(self):
        path = self.root / 'cpu-tests.json'
        row = dict(passed=True, layer_matches=384, layer_total=384, token_matches=64, tokens=[332]*64)
        cpu = dict(passed=True, device_executed=False, binary_sha256='host', real_model=dict(frozen=row, r5=row))
        self.write(path, cpu)
        build = dict(cpu_tests_sha256=w.sha(path), artifacts_sha256={'host/own-rt-iq3': 'host'})
        w.cpu_gate(path, build)
        cpu['real_model']['r5']['token_matches'] = 7
        self.write(path, cpu)
        with self.assertRaisesRegex(ValueError, 'changed since build'):
            w.cpu_gate(path, build)
        build['cpu_tests_sha256'] = w.sha(path)
        with self.assertRaisesRegex(ValueError, 'coverage incomplete'):
            w.cpu_gate(path, build)
    def test_cpu_binary_binding(self):
        path = self.root / 'cpu-tests.json'
        self.write(path, dict(passed=True, device_executed=False, binary_sha256='other'))
        with self.assertRaisesRegex(ValueError, 'binary identity mismatch'):
            w.cpu_gate(path, dict(cpu_tests_sha256=w.sha(path), artifacts_sha256={'host/own-rt-iq3': 'host'}))
    def test_native_identity_refused(self):
        hashes = self.fake_run()
        path = self.root / 'run/receipt.json'; native = w.read(path)
        native['device_executed'] = False; self.write(path, native)
        with self.assertRaisesRegex(ValueError, 'native run identity'):
            w.compare_run(self.root, w.CONFIG['W1'], hashes, [332]*8)


    def test_w1_is_direct_v2_eight_step_gate(self):
        self.assertEqual(w.CONFIG['W1']['count'], 8)
        self.assertEqual(w.CONFIG['W1']['steps'], 8)
        self.assertEqual(w.AUTHORITY, 'iq3-p17-detmath-v2')
        self.assertFalse(hasattr(w, 'baseline_gate'))

    def test_ldd_failure_is_prelaunch(self):
        def fake(*args, **kwargs):
            return type('Result', (), dict(returncode=0, stdout='libsycl.so => not found', stderr=''))()
        with self.assertRaisesRegex(ValueError, 'ldd dependency preflight failed'):
            w.ldd_preflight(Path('/never/run/device-binary'), fake)

    def test_ldd_success_never_executes_binary(self):
        calls = []
        def fake(argv, **kwargs):
            calls.append(argv)
            return type('Result', (), dict(returncode=0, stdout='libsycl.so => /some/libsycl.so', stderr=''))()
        w.ldd_preflight(Path('/never/run/device-binary'), fake)
        self.assertEqual(calls, [['ldd', '/never/run/device-binary']])

    def test_difference_receipt_has_all_layers_and_values(self):
        hashes = self.fake_run()
        oracle = self.root / 'oracle'
        (oracle / 'step1').mkdir(parents=True)
        (oracle / 'step1/layer-12.bf16').write_bytes(bytes([12])*20480)
        (self.root / 'run/step1/layer-12.bf16').write_bytes(b'x'*20480)
        diagnostics = {}
        with self.assertRaisesRegex(ValueError, 'first differing layer fixture'):
            w.compare_run(self.root, w.CONFIG['W1'], hashes, [332]*8, oracle, diagnostics)
        self.assertEqual(diagnostics['layer_total'], 384)
        self.assertEqual(diagnostics['layer_matches'], 383)
        first = diagnostics['first_differing_layer']
        self.assertEqual((first['step'], first['layer']), (1, 12))
        self.assertEqual(first['value_statistics']['unequal_values'], 10240)

    def test_missing_fixture_receipt_names_first_layer(self):
        hashes = self.fake_run()
        (self.root / 'run/step1/layer-04.bf16').unlink()
        result = w.compare_layers(self.root / 'run', None, hashes)
        self.assertEqual(result['first_differing_layer']['layer'], 4)
        self.assertEqual(result['layer_matches'], 383)


    def test_native_oracle_is_required_for_every_window(self):
        for name, cfg in w.CONFIG.items():
            if name == "W0": continue
            oracle = Path('/oracle/v2')
            cmd = w.native_command(Path('/never/run/device'), cfg, Path('/input'), '/weights', oracle, Path('/output'), 100)
            self.assertEqual(cmd[cmd.index('--oracle')+1], str(oracle))

    def test_debug_keys_present_even_empty_refused(self):
        for key in ('NEOReadDebugKeys','EnableDeferBacking','ForceUnknownFutureNeoOption'):
            for value in ('','0','1'):
                with self.assertRaisesRegex(ValueError,'before latch'):
                    w.environment_gate({'OMP_NUM_THREADS':'2',key:value})

    def test_environment_is_closed_and_recorded(self):
        e=w.environment_gate({'OMP_NUM_THREADS':'2','PATH':'/bin','CLAUDE_CODE_MESSAGING_TOKEN':'secret'})
        self.assertEqual(e['native'],{'OMP_NUM_THREADS':'2','PATH':'/bin'})
        self.assertNotIn('secret',json.dumps(e))

    def test_memory_floor_exact_boundary(self):
        census={'frozen':{'owned_peak_bytes_per_card':[10,20]}}
        floor=30+29321610240+12*1024**3
        self.assertEqual(w.memory_admission(census,'frozen',{'MemAvailable':floor,'GPUActive':99})['required_MemAvailable'],floor)
        with self.assertRaisesRegex(ValueError,'below'):
            w.memory_admission(census,'frozen',{'MemAvailable':floor-1,'GPUActive':99})

    def test_w0_requires_same_boot_binary_cards_environment(self):
        native=dict(schema='own-runtime.iq3.packet18.canary.v2',passed=True,device_executed=True,
                    owner_cards=2,round_trips=100,kernels_per_card=1000,token_sequence=True,
                    owned_device_bytes=1344,wall_ms=65000,max_submission_ns=1000,
                    startup_jit_ms=62000,device_work_ms=1,work_wall_ms=2999,teardown_ms=1,
                    submission_budget_passed=True,
                    teardown=[dict(safe_to_exit=True,live_bytes=0,in_flight=0)])
        self.write(self.root/'run/receipt.json',native)
        row=dict(schema='own-runtime.iq3.packet18.window.v1',window='W0',passed=True,
                 boot_id='boot',binary_sha256='bin',card=2,cards=2,environment={},
                 native_receipt_sha256=w.sha(self.root/'run/receipt.json'))
        path=self.root/'window.json';self.write(path,row)
        w.w0_gate(path,'bin','boot',2,{})
        for args in [('bad','boot',2,{}),('bin','old',2,{}),('bin','boot',1,{}),('bin','boot',2,{'changed':True})]:
            with self.assertRaisesRegex(ValueError,'changed'):w.w0_gate(path,*args)
        native['round_trips']=99;self.write(self.root/'run/receipt.json',native)
        with self.assertRaisesRegex(ValueError,'changed'):w.w0_gate(path,'bin','boot',2,{})

    def test_w0_receipt_missing_refused(self):
        with self.assertRaisesRegex(ValueError,'require --w0'):w.w0_gate(None,'','',2,{})

    def test_real_wrapper_rejects_neo_before_output_or_latch(self):
        import os, subprocess, sys
        for key in ('NEOReadDebugKeys','EnableDeferBacking','UnlistedNeoDebugOption'):
            out=self.root/key
            env=dict(os.environ,**{key:''})
            latch=HERE/'build/FAULT.json'
            before=latch.read_bytes() if latch.exists() else None
            result=subprocess.run([sys.executable,'-B',str(HERE/'window.py'),
                '--authorized-device-window','--window','W0','--seconds','600','--output',str(out)],
                env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('before latch',result.stderr)
            self.assertFalse(out.exists())
            self.assertEqual(latch.read_bytes() if latch.exists() else None,before)

    def test_memory_samples_keep_gpuactive_separate_from_rss(self):
        path=self.root/'meminfo';path.write_text('MemAvailable: 100 kB\nGPUActive: 20 kB\n')
        self.assertEqual(w.memory_snapshot(path),dict(MemAvailable=102400,GPUActive=20480,GPUActive_available=True))

    def test_pre_latch_environment_order(self):
        import inspect
        src=inspect.getsource(w.main)
        self.assertLess(src.index('environment_gate()'),src.index('ldd_preflight(binary)'))
        self.assertLess(src.index('ldd_preflight(binary)'),src.index('run_w0(a,'))
        self.assertLess(src.index('ldd_preflight(binary)'),src.index('out.mkdir('))

    def test_token_mismatch_receipt_survives_exception(self):
        hashes = self.fake_run()
        diagnostics = {}
        with self.assertRaisesRegex(ValueError, 'generated token: 1'):
            w.compare_run(self.root, w.CONFIG['W1'], hashes, [333]*8, diagnostics=diagnostics)
        self.assertEqual(diagnostics['first_differing_token'], 1)
        self.assertEqual(diagnostics['token_matches'], 0)
        self.assertEqual(w.token_diagnostics([], [332]*8)['first_differing_token'], 1)


if __name__ == '__main__': unittest.main()
