"""CPU-only screen contract, every-token gate, decision and passive plan tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import queue_runner as Q
import window as W
import suite_driver as D
import compare_screen as C
import test_suite_driver58 as fixtures

class ScreenTests(unittest.TestCase):
    def test_candidate_changes_only_down_layout(self):
        from views import VIEWS, selection
        self.assertEqual(VIEWS,('production','down-tile16'))
        before=D.read(selection('production'))['choices']
        after=D.read(selection('down-tile16'))['choices']
        self.assertEqual({k for k in before if before[k]!=after[k]},{'down'})
        self.assertEqual(after['down'],'down-tile16')
        self.assertEqual(after['route'],'route-exp32-rank4')
        self.assertEqual(after['recurrence'],'rows4-shared')
        self.assertEqual(Q.STAGES,(('production-before','production'),('down-tile16','down-tile16'),('production-after','production')))
    def test_one_model_launch_per_arm_and_fresh_k1(self):
        self.assertEqual(Q.ORDER,('K1a','K1b','WSCREEN'))
        for _,view in Q.STAGES:
            commands=Q.commands(Path('/tmp/test-only'),0,'2026-01-01T00:00:00Z','/lib',view)
            self.assertEqual(len(commands),3)
            self.assertEqual(sum(c[c.index('--window')+1]=='WSCREEN' for c in commands.values()),1)
            for name,cmd in commands.items():
                self.assertEqual(cmd[cmd.index('--view')+1],view)
                self.assertEqual(cmd.count('--k1'),2 if name=='WSCREEN' else 0)
                self.assertNotIn('--previous',cmd)
                self.assertEqual(cmd[cmd.index('-c')+1],'0-3,16-19' if name=='WSCREEN' else '8-15,24-31')
    def test_suite_command_is_full_128_and_one_native_owner(self):
        manifest=D.oracle_inputs()
        self.assertEqual(len(manifest['prompts']),12)
        for view in ('production','down-tile16'):
            for mode,expected in (('zerocopy','zero-copy'),('streamed','streamed')):
                args=SimpleNamespace(window='WSCREEN',view=view,output=Path('/tmp/synthetic'),miss_mode=mode)
                cmd=D.native_command(args,manifest,Path('/tmp/synthetic/table'))
                self.assertEqual(cmd[cmd.index('--max-new')+1],'128')
                self.assertEqual(cmd[cmd.index('--retain-steps')+1],'none')
                self.assertEqual(cmd[cmd.index('--miss-path')+1],expected)
                self.assertEqual(cmd[cmd.index('--cards')+1],'1')
                self.assertEqual(cmd[cmd.index('--native-nice')+1],'0')
                self.assertEqual(cmd.count('--suite-inputs'),1)
    def test_every_output_token_is_checked(self):
        # Exercise ALL positions, including the tail outside the timing interval.
        f=fixtures.SuiteTests();f.setUp()
        try:
            original=copy.deepcopy(f.record)
            for i in range(128):
                f.record=copy.deepcopy(original);f.record['tokens'][i]+=1000
                D.save(f.actual/'result.json',f.record)
                with self.assertRaisesRegex(ValueError,'token identity'):f.compare()
        finally:f.doCleanups()
    def test_k1_threshold_and_streamed_fallback(self):
        row=dict(cold_rotation=True,working_set_bytes=128*1024**2,passed=True,safe_to_exit=True,
            device_executed=True,zero_copy_supported=True,streamed_bytes_equal=True,
            exact_output_sha256='a'*64,zero_copy_bytes_equal=True,mixed_bytes_equal=True,
            bytes_per_iteration=25_000_000,host_ms=1,vram_ms=.1,streamed_ms=1.1)
        self.assertEqual(W.k1_summary(row,'a'*64)['selected_miss_path'],'zero-copy')
        row['host_ms']=3
        self.assertEqual(W.k1_summary(row,'a'*64)['selected_miss_path'],'streamed')
        row['streamed_bytes_equal']=False
        with self.assertRaises(ValueError):W.k1_summary(row,'a'*64)
    def test_both_fresh_k1_owners_required(self):
        with patch.object(W,'prerequisite',return_value=dict(pid=12,process_start_ticks=34)):
            with self.assertRaisesRegex(ValueError,'owners not fresh'):
                W.selected_miss_path([Path('/a/window.json'),Path('/b/window.json')],{})
        with self.assertRaisesRegex(ValueError,'two distinct'):
            W.selected_miss_path([Path('/a/window.json')]*2,{})
    def test_screen_uses_unchanged_timing_budget_and_whole_host(self):
        self.assertEqual(W.M.window_plan('WSCREEN'),W.M.window_plan('WS128'))
        self.assertEqual(W.M.window_plan('WSCREEN')['host_required_available_bytes'],118308908048)
        for name in Q.ORDER:self.assertEqual(W.A.window_scope(name),'whole-host')
    def test_plan_no_process_or_state_write(self):
        out=Q.ROOT/'production-before'
        with (patch.object(W,'build_gate',return_value={}),patch.object(Q.subprocess,'Popen',side_effect=AssertionError('launch')),
              patch.object(W.S,'journal',side_effect=AssertionError('journal'))):
            row=Q.plan(out,'production')
        self.assertFalse(out.exists());self.assertEqual(row['model_lifetimes'],1)
        self.assertEqual(row['planned_bracket_seconds'],[1980,2340])
        self.assertFalse(row['submission_eligible'])
    def test_no_retry_after_child_failure(self):
        with self.assertRaisesRegex(ValueError,'no retry'):Q.verify_success('WSCREEN',Path('/unused'),0,1)
    def test_review_rejects_future_boundary(self):
        with self.assertRaises(ValueError):W.S.fault_review('2099-01-01T00:00:00Z',1)
    def test_service_is_queue_owned(self):
        W.user_unit_gate('0::/user.slice/user@1000.service/app.slice/screen-packet58n-port-A.service')
        with self.assertRaises(ValueError):W.user_unit_gate('0::/system.slice/screen-packet58n-port-A.service')
    def test_memory_fence_read_only(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            for n in range(53,58):
                (p/f'memory{n}').mkdir();(p/f'memory{n}/state').write_text('offline')
            self.assertEqual(set(W.memory_fence(p).values()),{'offline'})
            (p/'memory54/state').write_text('online')
            with self.assertRaises(ValueError):W.memory_fence(p)
            self.assertEqual((p/'memory54/state').read_text(),'online')

class DecisionTests(unittest.TestCase):
    def rows(self,rates=(24.34,25.0,24.35)):
        return [{C.METRIC:dict(median=r), 'miss_path':'zero-copy',
                 'requests':[dict(prompt_id='fixture',prompt_token_sha256='a'*64,tokens=[1,2])]} for r in rates]
    def test_win_only_qualifies_full_chain(self):
        row=C.decision(self.rows());self.assertTrue(row['qualifies_for_full_chain'])
        self.assertFalse(row['submission_eligible']);self.assertFalse(row['realistic_final_gate']['passed'])
    def test_loss_drift_and_below_record_close_candidate(self):
        for rates in ((24.5,24.4,24.5),(24.,26.,25.),(23.,24.,23.)):
            r=C.decision(self.rows(rates));self.assertTrue(r['passed']);self.assertFalse(r['qualifies_for_full_chain'])
    def test_mismatch_refuses(self):
        rows=self.rows();rows[1]['requests'][0]['tokens']=[3]
        with self.assertRaisesRegex(ValueError,'tokens differ'):C.decision(rows)
        rows=self.rows();rows[1]['miss_path']='streamed'
        with self.assertRaisesRegex(ValueError,'paths differ'):C.decision(rows)
    def test_invalid_metric_refuses(self):
        for value in (True,float('nan'),0,float('inf')):
            with self.assertRaises(ValueError):C.decision(self.rows((24.,value,24.)))

if __name__=='__main__':unittest.main()
