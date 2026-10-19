"""Full census arithmetic and real file-lock protocol; no GPU/model reads."""
import io
import json
import signal
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import memory_plan as M
import window as W
import queue_runner as Q
import lane_admission as L
import onecard_admission as A
from drain_gate import DrainPermit, screen_teardown_admit


class Clock:
    value = 0
    def now(self): return self.value
    def sleep(self, seconds): self.value += seconds


class AdmissionTests(unittest.TestCase):
    def proc_owner(self, root, pid, pci):
        path=root/str(pid);(path/'fdinfo').mkdir(parents=True)
        (path/'stat').write_text(str(pid)+' (fixture) '+' '.join(['S']+['0']*18+['123']))
        (path/'fdinfo/3').write_text('drm-driver: xe\ndrm-pdev: '+pci+'\n')
        return path

    def test_adapter_holds_lane_and_drains_only_observed_card0(self):
        for name in Q.ORDER:
            with self.subTest(window=name), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
                # Every 58j window requires a whole-host gap.
                with A.Admission(name,root/'receipt',lambda:None,root=root/'lanes',
                                 drain_root=drain,proc=proc) as a:
                    self.assertTrue((root/'lanes/active-lane-A.json').exists())
                    a.before_launch()
                    owner=self.proc_owner(proc,42,'0000:23:00.0')
                    a.observe(dict(processes=[dict(pid=42)]))
                    self.assertTrue(a.owners['42']['seen'])
                    with self.assertRaisesRegex(ValueError,'remains after drain'): a.complete()
                    shutil.rmtree(owner)
                    a.complete()
                    self.assertTrue(a.record['passed'])
                self.assertFalse((root/'lanes/active-lane-A.json').exists())
                self.assertTrue(json.loads((drain/'teardown-state.json').read_text())['drained'])

    def test_adapter_rejects_foreign_timing_and_wrong_owned_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
            self.proc_owner(proc,43,'0000:43:00.0')
            with self.assertRaisesRegex(ValueError,'foreign Xe'):
                with A.Admission('WS128',root/'receipt',lambda:None,root=root/'lanes',
                                 drain_root=drain,proc=proc): pass
            self.assertFalse((root/'lanes/hold-lane-B').exists())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
            with A.Admission('KD',root/'receipt',lambda:None,root=root/'lanes',
                             drain_root=drain,proc=proc) as a:
                a.before_launch()
                self.proc_owner(proc,42,'0000:27:00.0')
                with self.assertRaisesRegex(ValueError,'another card'):
                    a.observe(dict(processes=[dict(pid=42)]))
            self.assertTrue((root/'lanes/active-lane-A.json').exists())

    def test_full_census_math_and_one_byte_boundary_every_window(self):
        for name in Q.ORDER:
            with self.subTest(window=name):
                p = M.window_plan(name)
                self.assertEqual(p['host_reserve_bytes'], 8*1024**3)
                required = p['host_required_available_bytes']
                M.admit({'MemAvailable':required, 'GPUActive':0}, p)
                with self.assertRaisesRegex(ValueError, 'host admission refused'):
                    M.admit({'MemAvailable':required-1, 'SwapFree':10**15}, p)
                if name not in ('K1a','K1b','WS128','WSCREEN'):
                    c = p['exact_host_categories']
                    self.assertEqual(c['pinned_packed_experts'], 48627712000)
                    self.assertEqual(c['device_backing_expert_cache_arena'], 18000000000)
                    self.assertEqual(c['device_backing_target_4k_bf16_kv_index'], 116391936)
                    self.assertEqual(sum(v for k,v in c.items() if k.startswith('device_backing_')),
                                     p['device_owned_bound_bytes'])
                    self.assertEqual(sum(c.values()) + M.HOST_RESERVE, required)
                    self.assertLess(required, 118308908048)
                    self.assertEqual(required, 85565068816)
                    self.assertFalse(p['shadow_observation']['complete_postload'])
        self.assertEqual(M.window_plan('WS128')['host_required_available_bytes'], 98990252032)

    def test_observed_shadow_cannot_remove_cache_or_kv_budget(self):
        p = M.exact_plan(dict(peak_shadow_bytes=0, complete_postload=True))
        q = M.exact_plan(dict(peak_shadow_bytes=123456, complete_postload=True))
        self.assertEqual(q['host_required_available_bytes']-p['host_required_available_bytes'],123456)
        self.assertGreater(p['host_required_available_bytes'], 48_627_712_000 + 26_409_219_600 + M.HOST_RESERVE)
        for value in (-1, float('nan'), True, 26_409_219_601):
            with self.assertRaises(ValueError): M.exact_plan(dict(peak_shadow_bytes=value))

    def test_each_window_waits_for_real_B_lease(self):
        for name in Q.ORDER:
            with self.subTest(window=name), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'lanes';clock=Clock();saw=[]
                with L.Reservation('B',root=root) as b:
                    def sleep(seconds):
                        self.assertTrue((root/'hold-lane-B').exists())
                        saw.append('held');b.complete(drained=True);clock.sleep(seconds)
                    with L.Reservation('A',window=name,root=root,now=clock.now,sleep=sleep) as a:
                        self.assertEqual(a.scope,'whole-host');self.assertTrue(saw)
                        a.complete(drained=True)
                self.assertFalse((root/'active-lane-A.json').exists())

    def test_timing_holds_B_before_wait_and_allows_current_screen_to_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'lanes'; clock=Clock(); saw=[]
            with L.Reservation('B',root=root) as b:
                def sleep(seconds):
                    self.assertTrue((root/'hold-lane-B').exists())
                    saw.append('held-before-B-drain')
                    b.complete(drained=True)
                    clock.sleep(seconds)
                with L.Reservation('A',window='WS128',root=root,now=clock.now,sleep=sleep) as a:
                    self.assertEqual(a.scope,'whole-host')
                    self.assertTrue(saw)
                    blocker=Clock()
                    with self.assertRaisesRegex(ValueError,'timed out'):
                        L.Reservation('B',root=root,now=blocker.now,sleep=blocker.sleep,wait_seconds=1).__enter__()
                    a.complete(drained=True)
            self.assertFalse((root/'hold-lane-B').exists())

    def test_failed_admission_retains_owned_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'lanes'
            with L.Reservation('A',window='WS128',root=root): pass
            self.assertTrue((root/'hold-lane-B').exists())
            with self.assertRaisesRegex(ValueError,'coordinator review'):
                L.Reservation('A',window='KD',root=root).__enter__()

    def test_shared_drain_compatibility_with_lane_B(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'lanes'; drain=Path(tmp)/'drain';drain.mkdir()
            with L.Reservation('A',window='KD',root=root) as a:
                with DrainPermit(Path(tmp)/'receipt',root=drain,reservation=a.record) as d:
                    clock=Clock()
                    with self.assertRaisesRegex(ValueError,'timed out'):
                        L.Reservation('B',root=root,now=clock.now,sleep=clock.sleep,wait_seconds=1).__enter__()
                    with self.assertRaisesRegex(FileNotFoundError,'active-lane-B.json'):
                        screen_teardown_admit('B',root=drain,coordination_root=root)
                    # Even a stray B marker must not enable overlap with this
                    # whole-host reservation. Only this temporary fixture changes.
                    (root/'active-lane-B.json').write_text('{}')
                    with self.assertRaisesRegex(ValueError,'shared drain is not this live A exactness reservation'):
                        screen_teardown_admit('B',root=drain,coordination_root=root)
                    (root/'active-lane-B.json').unlink()
                    d.complete()
                a.complete(drained=True)

    def test_reserve_crossing_sends_only_cooperative_sigterm(self):
        class Child:
            pid=123; returncode=None
            signals=[]
            def poll(self): return self.returncode
            def send_signal(self,sig): self.signals.append(sig);self.returncode=1
        child=Child(); reasons=[]; clock=Clock(); log=io.StringIO()
        def sensor(pid):
            return W.account_memory(dict(root_seen=True,anonymous_bytes=0),
                dict(MemAvailable=M.HOST_RESERVE-1,GPUActive=0),0,0,M.window_plan('KD'))
        result=W.S.supervise(child,60,None,log,reasons,lambda r:None,lambda:None,
            read_journal=lambda cursor:('',cursor), now=clock.now,sleep=clock.sleep,
            memory_sensor=sensor)
        self.assertEqual(child.signals,[signal.SIGTERM])
        self.assertFalse(result['child_still_running'])
        self.assertTrue(any('8 GiB stop floor' in r for r in reasons))

    def test_postload_proof_requires_cache_KV_and_after_load(self):
        p=M.window_plan('KD')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'run/run';run.mkdir(parents=True)
            rows=json.loads((W.HERE/'evidence/postload-census.json').read_text())
            for allocation in rows['allocations']:
                if allocation['label']=='card0:immutable-expert-cache':allocation['bytes']=M.CACHE_BYTES
            rows['allocations'].append(dict(label='card0:exact-half-decode-table',category='weights',memory='device',bytes=262144,live=True))
            # Full metadata extents, including the KV preceding cache setup.
            rows['allocations'].append(dict(label='card0:KV',category='KV',memory='device',bytes=116391936,live=True))
            (run/'census.json').write_text(json.dumps([rows]))
            (run/'progress.jsonl').write_bytes((W.HERE/'lineage/fixtures/58c-kd/run/progress.jsonl').read_bytes())
            (root/'host-memory.jsonl').write_text(json.dumps(dict(host=dict(GPUActive=48627772000),
                pinned_expert_bytes=48627712000,gpuactive_shadow_bytes=60000))+'\n')
            sample=dict(phase='after_load',GPUActive=48627772000,MemAvailable=10*M.GIB)
            (run/'host-memory.jsonl').write_text(json.dumps(sample)+'\n')
            result=W.postload_observation(root,p,dict(baseline_gpuactive_bytes=0))
            self.assertTrue(result['complete_postload'])
            self.assertEqual(result['after_load_shadow_bytes'],60000)
            sample['phase']='end'
            (run/'host-memory.jsonl').write_text(json.dumps(sample)+'\n')
            with self.assertRaisesRegex(ValueError,'after_load'):
                W.postload_observation(root,p,dict(baseline_gpuactive_bytes=0))
            sample['phase']='after_load'
            (run/'host-memory.jsonl').write_text(json.dumps(sample)+'\n')
            rows['allocations'].pop()
            (run/'census.json').write_text(json.dumps([rows]))
            with self.assertRaisesRegex(ValueError,'KV'):
                W.postload_observation(root,p,dict(baseline_gpuactive_bytes=0))

    def test_card0_only_and_fixed_gaps(self):
        self.assertEqual(Q.GAP_SECONDS,90)
        with self.assertRaises(ValueError): Q.commands(Path('/tmp/unused'),2,'2026-01-01T00:00:00Z','')
        self.assertEqual([L.window_scope(n) for n in Q.ORDER], ['whole-host']*3)
        for name in Q.ORDER:
            cmd=Q.commands(Path('/tmp/unused'),0,'2026-01-01T00:00:00Z','')[name]
            self.assertEqual(cmd[cmd.index('--card')+1],'0')


if __name__ == '__main__': unittest.main()
