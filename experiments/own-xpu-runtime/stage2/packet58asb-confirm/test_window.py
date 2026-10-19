import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import window as W
import queue_runner as Q

class WindowTests(unittest.TestCase):
    def test_plan_requires_postload_gate(self):
        output=Q.P/'evidence/never-created-cpu-test'
        with patch.object(W,'build_gate',side_effect=ValueError('post-load allocation gate required')) as gate:
            with self.assertRaisesRegex(ValueError,'post-load allocation gate required'):
                Q.main(['--plan','--card','0','--output-root',str(output),
                        '--faults-reviewed-through','2026-01-01T00:00:00Z'])
            gate.assert_called_once_with()
        self.assertFalse(output.exists())
    def test_build_refuses_missing_postload_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,
                     sources={'fixture':'digest'},artifacts={'build/device/own-rt-iq3':'a','build/device/p58-cache-fixtures':'b'},gates={})
            (root/'build-receipt.json').write_text(json.dumps(row))
            with patch.object(W,'HERE',root),patch.object(W,'verify_files'):
                with self.assertRaisesRegex(ValueError,'post-load allocation gate required'):W.build_gate()
    def test_closed_environment(self):
        self.assertEqual(W.closed_environment({'LD_LIBRARY_PATH':json.loads((W.HERE/'library-path.json').read_text())['LD_LIBRARY_PATH'],'PATH':'/usr/bin:/bin'})['OMP_NUM_THREADS'],'2')
        for env in ({'LD_LIBRARY_PATH':json.loads((W.HERE/'library-path.json').read_text())['LD_LIBRARY_PATH'],'NEOReadDebugKeys':'1'},{'LD_LIBRARY_PATH':json.loads((W.HERE/'library-path.json').read_text())['LD_LIBRARY_PATH'],'PATH':'/tmp'},{'LD_LIBRARY_PATH':json.loads((W.HERE/'library-path.json').read_text())['LD_LIBRARY_PATH'],'OMP_NUM_THREADS':'32'}):
            with self.assertRaises(ValueError):W.closed_environment(env)
    def test_memory_fence_margin_may_stay_online(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for n in range(53,58):
                (root/f'memory{n}').mkdir();(root/f'memory{n}'/'state').write_text('offline' if n in (54,56) else 'online')
            self.assertEqual(W.memory_fence(root)['57'],'online')
            (root/'memory54/state').write_text('online')
            with self.assertRaises(ValueError):W.memory_fence(root)
    def test_fault_boundary_not_future_or_local(self):
        now=time.time_ns()//1000
        for value in ('2099-01-01T00:00:00Z','2026-01-01T00:00:00-04:00'):
            with self.assertRaises(ValueError):W.S.fault_review(value,now)
        self.assertEqual(W.S.fault_review('2026-01-01T00:00:00Z',now)[0],'2026-01-01T00:00:00Z')
    def test_pf_exiting_sensor(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pid=root/'42';pid.mkdir()
            (pid/'status').write_text('State:\tR (running)\n')
            (pid/'stat').write_text('42 (worker name) R 1 1 1 1 1 4 0 0')
            self.assertTrue(W.SUPPORT._exited_status(root,42))
            (pid/'stat').write_text('42 (worker name) R 1 1 1 1 1 0 0 0')
            self.assertFalse(W.SUPPORT._exited_status(root,42))
    def test_k1_selection(self):
        row=dict(cold_rotation=True,working_set_bytes=128*1024**2,passed=True,safe_to_exit=True,device_executed=True,zero_copy_supported=True,streamed_bytes_equal=True,exact_output_sha256='a'*64,zero_copy_bytes_equal=True,mixed_bytes_equal=True,bytes_per_iteration=25_000_000,host_ms=1,vram_ms=.1,streamed_ms=1.1)
        self.assertEqual(W.k1_summary(row,cpu_digest='a'*64)['selected_miss_path'],'zero-copy')
        row['host_ms']=3
        self.assertEqual(W.k1_summary(row,cpu_digest='a'*64)['selected_miss_path'],'streamed')
        row['zero_copy_bytes_equal']=False
        with self.assertRaises(ValueError):W.k1_summary(row,cpu_digest='a'*64)
    def test_nonfinite_k1_time(self):
        row=dict(cold_rotation=True,working_set_bytes=128*1024**2,passed=True,safe_to_exit=True,device_executed=True,zero_copy_supported=True,streamed_bytes_equal=True,exact_output_sha256='a'*64,zero_copy_bytes_equal=True,mixed_bytes_equal=True,bytes_per_iteration=1,host_ms=float('nan'),vram_ms=1,streamed_ms=1)
        with self.assertRaises(ValueError):W.k1_summary(row,cpu_digest='a'*64)
    def test_selected_card_passive(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fd=root/'42/fdinfo';fd.mkdir(parents=True)
            (fd/'3').write_text('drm-driver: xe\ndrm-pdev: 0000:43:00.0\n')
            self.assertEqual(len(W.selected_clients(0,root)['other']),1)
            with self.assertRaises(ValueError):W.selected_clients(2,root)
            (fd/'3').write_text('drm-driver: xe\n')
            with self.assertRaises(ValueError):W.selected_clients(0,root)
    def test_service_scope(self):
        W.user_unit_gate('0::/user.slice/user-1000.slice/user@1000.service/app.slice/packet58-onecard-58as-b.service')
        for s in ('0::/system.slice/packet58-onecard-58as-b.service','0::/user.slice/user@1000.service/app.slice/packet57-run.service'):
            with self.assertRaises(ValueError):W.user_unit_gate(s)
    def test_queue_single_card_no_mtp(self):
        commands=Q.commands(Path('/tmp/evidence'),0,'2026-01-01T00:00:00Z','/lib')
        self.assertEqual(tuple(commands),Q.ORDER)
        for name,c in commands.items():
            self.assertEqual(c[c.index('--card')+1],'0')
            self.assertNotIn('--draft-rank',c)
            self.assertEqual(c.count('--k1'),0 if name.startswith('K1') else 2)
    def test_native_card_mask_index(self):
        from argparse import Namespace
        c=W.native_command(Namespace(window='K1',card=2),Path('/tmp/o'),None)
        self.assertEqual(c[c.index('--card')+1],'0')
    def test_identity_path_escape(self):
        for p in ('../other','/tmp/other'):
            with self.assertRaises(ValueError):W.safe_path(Path('/tmp/packet'),p)
    def test_prerequisite_tamper_and_owner(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'run').mkdir();native=root/'run/k1.json';native.write_text('{}')
            for leaf in ('run/k1-cases.jsonl','summary.json','kernel-before.jsonl','kernel-window.jsonl'):(root/leaf).write_text('{}')
            files={str(p.relative_to(root)):W.sha(p) for p in root.rglob('*') if p.is_file()}
            identity=dict(boot_id='boot',build_receipt_sha256='seal',artifacts_sha256={'binary':'hash'},environment={'x':'y'},card=0,context=4096,gpu_count=1)
            row=dict(identity,schema='own-runtime.packet58.window.v1',passed=True,device_executed=True,child_still_running=False,window='K1',qualifying=False,stop_reasons=[],pid=42,process_start_ticks=123,native_files=files)
            row['lane_admission']=dict(passed=True,card=0,scope='whole-host',timing_claim_eligible=False,reservation=dict(boot_id='boot'))
            p=root/'window.json';p.write_text(json.dumps(row))
            self.assertEqual(W.prerequisite(p,'K1',identity)['pid'],42)
            with self.assertRaises(ValueError):W.prerequisite(p,'K1',dict(identity,card=2))
            with self.assertRaisesRegex(ValueError,'build_receipt_sha256'):W.prerequisite(p,'K1',dict(identity,build_receipt_sha256='new-wrapper-seal'))
            native.write_text('{"tampered":true}')
            with self.assertRaises(ValueError):W.prerequisite(p,'K1',identity)
    def test_same_k1_owner_refused(self):
        row=dict(pid=42,process_start_ticks=123)
        with patch.object(W,'prerequisite',return_value=row):
            with self.assertRaisesRegex(ValueError,'owners not fresh'):
                W.selected_miss_path([Path('/a/window.json'),Path('/b/window.json')],{})
    def test_queue_never_accepts_failed_child(self):
        with self.assertRaisesRegex(ValueError,'no retry'):
            Q.verify_success('K1a',Path('/does-not-exist'),0,75)
    def test_memory_floor_graceful_supervisor_signal(self):
        sample=dict(root_seen=True,anonymous_bytes=0)
        with patch.object(W.SUPPORT,'process_tree_anon',return_value=sample),patch.object(W.M,'meminfo',return_value={'MemAvailable':1}):
            with self.assertRaisesRegex(ValueError,'8 GiB stop floor'):
                W.live_memory_sensor(42,budget={'device_owned_bound_bytes':100})
    def test_watchdogs_not_speed_claims(self):
        for expected,watchdog in W.CONFIG.values():self.assertGreaterEqual(watchdog,3*expected)

if __name__=='__main__':unittest.main()
