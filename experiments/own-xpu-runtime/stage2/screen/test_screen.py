"""CPU-only regression tests: fake native owners; never open a device."""
import io
import json
from pathlib import Path
import tempfile
import sys
import types
import unittest
from unittest.mock import patch

import common as C
import screen as W
import seal
import tp2_worker


class ScreenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def rows(self):
        rows = []
        for index, prompt in enumerate(C.D.CHECK.PROMPT_IDS):
            stamps = [10 + i * .02 for i in range(128)]
            result = dict(tokens=list(range(128)), timing_rows=[dict(completed_monotonic=t) for t in stamps])
            row = C.METRICS.request_metrics(result, 60, 128, 'none', start=9., end=13., device=True)
            row.update(passed=True, prompt_id=prompt, prompt_class=C.METRICS.PROMPT_CLASSES[prompt],
                       stats=dict(guesses=70, hits=56, misses=14, no_guess=1), acceptance=.8,
                       hit_miss_cycles={'hit': {'mean_ms': 18}, 'miss': {'mean_ms': 33}})
            rows.append(row)
        return rows

    def test_ws128_formulas_and_diagnostic_labels(self):
        rows = self.rows()
        inherited = C.METRICS.aggregate(rows)
        result = C.summary(rows, dict(passed=True), 'tp2')
        for key in ('class_balanced_tok_s_1_100_intervals_after_ttft', 'submission100_statistics',
                    'acceptance_statistics', 'hit_miss_cycle_statistics'):
            self.assertEqual(result[key], inherited[key])
        self.assertAlmostEqual(result['submission100_statistics']['median'], 50.)
        self.assertEqual(rows[0]['submission100']['numerator'], 99)
        self.assertFalse(result['submission_eligible'])
        self.assertFalse(result['realistic_final_gate']['passed'])
        self.assertNotIn('raw_payload_fields', result)
        self.assertTrue(all(r['diagnostic'] and not r['speed_evidence_eligible'] for r in result['requests']))

    def test_class_balance_not_pooled_median(self):
        rows = self.rows()
        for row in rows:
            row['tok_s_1_100_intervals_after_ttft'] = {'code':10, 'operations':10, 'analysis':10,
                'prose':100, 'documentation':100, 'structured-writing':100}[row['prompt_class']]
        result = C.summary(rows, dict(passed=True), 'tp2')
        self.assertEqual(result['submission100_statistics']['median'], 10)
        self.assertEqual(result['class_balanced_tok_s_1_100_intervals_after_ttft']['median'], 55)

    def test_every_token_including_last_must_match(self):
        expected = list(range(128))
        for index in (0, 63, 99, 127):
            tokens = expected.copy(); tokens[index] = -1
            with self.assertRaises(ValueError): C.compare_tokens(tokens, expected, 128, 'test')
        with self.assertRaises(ValueError): C.compare_tokens(expected[:-1], expected, 128, 'test')

    def test_partial_or_reordered_suite_refused(self):
        for rows in (self.rows()[:-1], list(reversed(self.rows()))):
            with self.assertRaises(ValueError): C.summary(rows, dict(passed=True), 'tp2')

    def test_prefix_reads_only_complete_lines_and_rejects_mismatch(self):
        out = self.root; dest = out / 'run/incident-retrospective'; dest.mkdir(parents=True)
        path = dest / 'timings.jsonl'
        manifest = {'prompts': [{'prompt_id':'incident-retrospective'}]}
        lines = [json.dumps(dict(generated_index=i+1, token_id=i))+'\n' for i in range(64)]
        with patch.object(C.D.CHECK, 'token_record', return_value=list(range(128))):
            path.write_text(''.join(lines[:63])+'{"partial":')
            self.assertIsNone(W.prefix_check(out, manifest))
            path.write_text(''.join(lines)+'{"partial":')
            self.assertEqual(W.prefix_check(out, manifest)['tokens_compared'], 64)
            path.write_text(''.join(lines).replace('"token_id": 63', '"token_id": 999'))
            with self.assertRaises(ValueError): W.prefix_check(out, manifest)

    def test_closed_environment_and_review_boundary(self):
        env = dict(PATH='/usr/bin:/bin', OMP_NUM_THREADS='2', LD_LIBRARY_PATH='/approved')
        self.assertEqual(C.W.closed_environment(env), env)
        for extra in ({'SECRET':'hidden'}, {'ZE_AFFINITY_MASK':'0'}, {'OMP_NUM_THREADS':'4'}):
            with self.assertRaises(ValueError): C.W.closed_environment(dict(env, **extra))
        for stamp in ('2099-01-01T00:00:00Z', '2026-01-01T00:00:00-04:00', '2026-01-01'):
            with self.assertRaises(ValueError): C.S.fault_review(stamp, 1792238705000000)

    def test_5456_fence_only_and_fail_closed(self):
        for n in range(53,58):
            dest = self.root / f'memory{n}'; dest.mkdir()
            (dest/'state').write_text('offline' if n in (54,56) else 'online')
        self.assertEqual(C.W.memory_fence(self.root)['53'], 'online')
        (self.root/'memory56/state').write_text('online')
        with self.assertRaises(ValueError): C.W.memory_fence(self.root)

    def test_pf_exiting_root_is_not_broken_sensor(self):
        sample = dict(root_seen=False, anonymous_bytes=0)
        with patch.object(C.SUPPORT, 'process_tree_anon', return_value=sample), \
             patch.object(C.SUPPORT, '_exited_status', return_value=True), \
             patch.object(C.M, 'meminfo', return_value={'MemAvailable':10*C.M.GIB}):
            self.assertTrue(W.memory_sensor(123, 'tp2', {})['root_pf_exiting_or_gone'])

    def test_live_missing_sensor_not_excused(self):
        with patch.object(C.SUPPORT, 'process_tree_anon', return_value=dict(root_seen=False, anonymous_bytes=0)), \
             patch.object(C.SUPPORT, '_exited_status', return_value=False), \
             patch.object(C.M, 'meminfo', return_value={'MemAvailable':10*C.M.GIB}):
            self.assertFalse(W.memory_sensor(123, 'tp2', {})['root_seen'])

    def test_fault_supervision_sigterm_once_no_retry_and_retains(self):
        class Child:
            pid = 7
            signals = []
            def poll(self): return None
            def send_signal(self, sig): self.signals.append(sig)
        child = Child(); now = [0.]; reasons = []; latches = []
        def sleep(n): now[0] += n
        result = C.S.supervise(child, 100, 'cursor', io.StringIO(), reasons, latches.append, lambda:None,
            read_journal=lambda cursor: ('Fault response\n', cursor), now=lambda:now[0], sleep=sleep,
            drain_seconds=1, memory_sensor=lambda pid:dict(root_seen=True, anonymous_bytes=0))
        self.assertTrue(result['child_still_running'])
        self.assertEqual(child.signals, [W.signal.SIGTERM])
        self.assertTrue(latches)

    def test_unit_gate(self):
        W.unit_gate('0::/user.slice/user-1000.slice/user@1000.service/app.slice/screen-p56-a.service')
        with self.assertRaises(ValueError): W.unit_gate('0::/user.slice/session-1.scope')

    def test_onecard_command_one_process_no_captures(self):
        args = W.parser().parse_args(['--profile','onecard','--lineage',str(C.P58),
            '--output',str(self.root),'--faults-reviewed-through','2026-10-17T00:00:00Z','--incident-prefix'])
        manifest = C.D.oracle_inputs()
        identity = dict(binary='/sealed/engine', dispatch='/sealed/dispatch', selection_sha256='a'*64)
        cmd = W.command(args, identity, manifest)
        self.assertEqual(cmd.count('/sealed/engine'), 1)
        for key,value in [('--retain-steps','none'),('--max-new','128'),('--cards','1'),('--miss-path','streamed')]:
            self.assertEqual(cmd[cmd.index(key)+1],value)

    def test_legacy_dispatch_tampering_refused(self):
        path = self.root/'changed-dispatch.json'
        original = C.read(C.P56/'dispatch-speed6.json')
        original['classes']['streams'] = 'packet18'
        C.save(path, original)
        args = types.SimpleNamespace(lineage=C.P56,seal=None,binary=None,dispatch=path,profile='tp2')
        with self.assertRaisesRegex(ValueError, 'pinned production dispatch'):
            C.sealed(args)

    def test_lean_seal_binds_build_fixture_and_rejects_changed_bytes(self):
        root = self.root
        for name in ('binary','source.cpp','selection.json','memory-plan.json','dispatch.json','expected.bin','actual.bin'):
            (root/name).write_bytes(b'{}' if name.endswith('.json') else b'exact')
        sources = {'source.cpp':C.sha(root/'source.cpp')}
        build = dict(passed=True,device_executed=False,sources=sources,artifacts={'binary':C.sha(root/'binary')})
        C.save(root/'build.json',build)
        fixture = dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
            changed_class='expert GEMV',command=['fixture'],sources=sources,build_receipt_sha256=C.sha(root/'build.json'),
            expected={'path':'expected.bin','sha256':C.sha(root/'expected.bin')},
            actual={'path':'actual.bin','sha256':C.sha(root/'actual.bin')})
        C.save(root/'fixture.json',fixture)
        with patch.object(seal,'ROOT',root):
            seal.create(root,'tp2',root/'build.json',root/'fixture.json',root/'binary',root/'dispatch.json',root/'seal.json')
            self.assertEqual(C.read(root/'seal.json')['qualification'],'screen only; no full-chain qualification')
            C.verify_map(root,C.read(root/'seal.json')['fixture_files'])
            (root/'actual.bin').write_bytes(b'different')
            with self.assertRaises(ValueError): C.verify_map(root,C.read(root/'seal.json')['fixture_files'])
            with self.assertRaises(ValueError):
                seal.create(root,'tp2',root/'build.json',root/'fixture.json',root/'binary',root/'dispatch.json',root/'seal2.json')

    def test_tp2_single_pair_load_13_resets_one_close(self):
        sys.path.insert(0, str(C.P56))
        import pipeline
        import suite
        import storage
        out = self.root / 'run'
        entries = [{'prompt_id':pid} for pid in C.D.CHECK.PROMPT_IDS]
        snapshots = {e['prompt_id']:(self.root,[1,2,3]) for e in entries}
        calls = []
        class Transport:
            def __init__(self, args, ranks, env, check):
                calls.append(('load', args.tokens, args.retain_steps))
            def close(self, success): calls.append(('close',success))
        def reset(transport, dest):
            dest.mkdir(); calls.append(('reset', dest.name))
        def request(transport,args,prompt,count):
            calls.append(('request',count))
            row = self.rows()[0]
            row.update(tokens=list(range(count)), stats={}, hit_miss_cycles={})
            return row
        identity = dict(lineage=str(C.P56),binary='/sealed/binary',dispatch='/sealed/dispatch',selection_sha256='a'*64)
        old_p, old_sp, old_sb, old_admit = pipeline.P, storage.P, storage.B, storage.admit
        try:
            with patch.object(C.D,'oracle_inputs',return_value={'prompts':entries}), \
                 patch.object(C.D.CHECK,'token_record',return_value=list(range(128))), \
                 patch.object(pipeline,'Transport',Transport), \
                 patch.object(suite,'checker_module',return_value=object()), \
                 patch.object(suite,'admit_inputs',return_value=snapshots), \
                 patch.object(suite,'reset',side_effect=reset), \
                 patch.object(suite,'run_request',side_effect=request):
                self.assertEqual(tp2_worker.run(identity,out,3600),0)
        finally:
            pipeline.P, storage.P, storage.B, storage.admit = old_p, old_sp, old_sb, old_admit
            sys.path.remove(str(C.P56))
        self.assertEqual([r for r in calls if r[0]=='load'], [('load',128,'none')])
        self.assertEqual([r[1] for r in calls if r[0]=='request'], [64]+[128]*12)
        self.assertEqual([r for r in calls if r[0]=='close'], [('close',True)])
        self.assertEqual(len([r for r in calls if r[0]=='reset']),14)
        self.assertTrue(C.read(out/'summary.json')['passed'])

    def test_plan_cannot_launch_or_make_outputs(self):
        args = ['--profile','tp2','--lineage',str(C.P56),'--output',
                str(C.HERE/'evidence/test-plan-no-write'),'--faults-reviewed-through',
                '2026-10-17T00:00:00Z','--plan']
        with patch.object(W.subprocess,'Popen',side_effect=AssertionError('launch in plan')), \
             patch.object(W.S,'journal',side_effect=AssertionError('journal in plan')), \
             patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(W.main(args),0)
        self.assertFalse((C.HERE/'evidence/test-plan-no-write').exists())


if __name__ == '__main__':
    unittest.main()
