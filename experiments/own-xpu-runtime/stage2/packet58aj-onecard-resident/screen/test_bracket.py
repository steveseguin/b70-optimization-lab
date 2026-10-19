import copy,json,tempfile,unittest,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import views as V
import suite_driver as D
import queue_runner as Q
import window as W
from compare_bracket import compare
from owner_teardown import finish_model_owner
import test_admission58e as F


class BracketPolicyTests(unittest.TestCase):
    def test_all_views_keep_storage(self):
        for view in V.VIEWS:
            choices=V.validate(view)['choices']
            self.assertEqual(choices['down'],'down-tile16')
            self.assertEqual(choices['hc'],'mapped')
        for name in ('fused','mapped','half-cache','tile16'):
            with self.assertRaises(ValueError):V.bracket(name)

    def test_unknown_extra_or_changed_choice_refused(self):
        row=V.validate('mapped')
        for bad in (dict(row,extra=True),dict(row,choices=dict(row['choices'],other_fusion='fused')),
                    dict(row,choices=dict(row['choices'],down='mapped'))):
            with patch('views.json.loads',return_value=bad),self.assertRaises(ValueError):V.selection('tile16')

    def rows(self,rates=(25,26,25,26,25)):
        return [dict(label=label,passed=True,requests=[dict(exact_oracle=True,cached_tokens=0) for _ in range(12)],
                class_balanced_tok_s_1_100_intervals_after_ttft=dict(median=rate))
                for label,rate in zip(('A0','B0','A1','B1','A2'),rates)]

    def test_two_candidates_must_beat_every_control(self):
        self.assertTrue(compare(self.rows())['candidate_beats_all_controls'])
        for rates in ((25,26,25,25,25),(25,26,26,26,25),(25,26,25,26,26)):
            self.assertFalse(compare(self.rows(rates))['candidate_beats_all_controls'])
        self.assertFalse(compare(self.rows((25,27,26,27,25)))['control_drift_passed'])

    def test_inexact_or_incomplete_or_cached_refuses(self):
        for mutation in (lambda x:x.pop(),lambda x:x[1]['requests'].pop(),
                         lambda x:x[0]['requests'][0].update(exact_oracle=False),
                         lambda x:x[1]['requests'][11].update(exact_oracle=False),
                         lambda x:x[3]['requests'][0].update(cached_tokens=1)):
            rows=self.rows();mutation(rows)
            with self.assertRaises(ValueError):compare(rows)

    def test_cold_first_view_is_reported_but_excluded(self):
        result=compare(self.rows((22.730951,28.115842,26.053436,28.152570,26.078853)))
        self.assertTrue(result['candidate_beats_all_controls'])
        self.assertEqual(result['comparison_controls'],['A1','A2'])
        self.assertEqual(result['warmup_view'],dict(label='A0',rate=22.730951,exact=True,
                         excluded_from_drift_and_comparison=True))
        self.assertGreater(result['minimum_gain_vs_best_control'],.078)

    def test_each_candidate_must_clear_warm_controls(self):
        for rates in ((22,25.974,26,28,26),(22,28,26,25.974,26)):
            self.assertFalse(compare(self.rows(rates))['candidate_beats_all_controls'])

    def test_warm_drift_three_point_five_percent_fails(self):
        self.assertFalse(compare(self.rows((22,28,26,28,26.91)))['control_drift_passed'])

    def test_inclusive_decimal_thresholds(self):
        for rates in ((1,25.5,25,25.5,25),(1,27,25,27,25.75)):
            self.assertTrue(compare(self.rows(rates))['candidate_beats_all_controls'])
        self.assertFalse(compare(self.rows((1,25.499999,25,25.5,25)))['candidate_beats_all_controls'])
        self.assertFalse(compare(self.rows((1,27,25,27,25.750001)))['control_drift_passed'])

    def test_no_fresh_process_or_submission_claim(self):
        row=compare(self.rows())
        self.assertFalse(row['fresh_process_repeat']);self.assertFalse(row['submission_eligible'])

    def test_whole_host_and_watchdog(self):
        for stage in Q.ORDER:
            name='K1' if stage.startswith('K1') else stage
            self.assertEqual(W.A.window_scope(name),'whole-host')
            self.assertGreaterEqual(W.CONFIG[name][1],4*W.CONFIG[name][0])
        self.assertGreaterEqual(W.CONFIG['WSCREEN'][1],4*1800)
        self.assertEqual(W.M.window_plan('WSCREEN')['host_required_available_bytes'],98_990_252_032)
        self.assertEqual(W.M.plan()['device_owned_bound_bytes'],29_963_128_848)

    def test_runtime_disk_reserve_at_25gb_boundary(self):
        for free,allowed in ((24_999_999_999,False),(25_000_000_000,False),(25_000_001_024,True)):
            with patch.object(W.shutil,'disk_usage',return_value=SimpleNamespace(free=free)),patch.object(W.SUPPORT,'storage',return_value={}):
                if allowed:self.assertEqual(W.storage(Path('/scratch'),1024)['root_stop_floor_bytes'],25_000_000_000)
                else:
                    with self.assertRaisesRegex(ValueError,'25 GB'):W.storage(Path('/scratch'),1024)

    def test_fresh_window_process_installs_full_fault_policy(self):
        code=('import window as W; W.install_fault_policy(); '
              'assert all(W.S.FAULT.search(s) for s in ("GuC reset", "GPU HANG", "wedged", "Fault response")); '
              'assert not W.S.FAULT.search("ordinary progress")')
        subprocess.run([sys.executable,'-B','-c',code],cwd=W.HERE,stdin=subprocess.DEVNULL,check=True)

    def test_oracle_completion_replacement_refused(self):
        original=D.read
        def changed(path):
            row=original(path)
            return dict(row,completion_sha256='0'*64) if Path(path)==D.HERE/'oracle-binding.json' else row
        with patch.object(D,'read',side_effect=changed),self.assertRaisesRegex(ValueError,'registered oracle completion changed'):
            D.oracle_inputs()


class SummaryTests(unittest.TestCase):
    """Replay actual 60-request checker with synthetic native receipts in scratch."""
    @classmethod
    def setUpClass(cls):cls.manifest=D.oracle_inputs()

    def fixture(self,out,candidate="p60fusion"):
        cap=64 if candidate=="smoke" else 128
        run=out/'run';run.mkdir()
        native=dict(passed=True,safe_to_exit=True,device_executed=True,owner_cards=1,
            cpu_affinity=[0,1,2,3,16,17,18,19],observed_nice=0,native_nice=0,
            teardown=[dict(safe_to_exit=True,idle_marker_complete=True,exit_code=0,live_bytes=0,in_flight=0)])
        D.save(run/'receipt.json',native)
        for label,view in V.bracket(candidate):
            folder=run/label;folder.mkdir()
            D.save(folder/'boundary.json',dict(passed=True,cache_maintenance=V.DEFAULT_MAINTENANCE,cache_cap="max",hc=view,cache_allocation_bytes=V.MAX_BYTES,cache_started_empty=True,selection_sha256=V.digest(view),allocation_ids_preserved=True,
                weight_uploads_during_switch=0,model_loads=1,context_extent=32,arena_descriptors_sha256='a'*64,weight_descriptors_sha256='b'*64))
            for e in self.manifest['prompts']:
                actual=folder/e['prompt_id'];actual.mkdir()
                tokens=D.CHECK.token_record(D.ORACLE/'results'/e['prompt_id'])[:cap]
                interval=.038 if label.startswith('B') else .04
                D.save(actual/'result.json',dict(passed=True,arithmetic=D.ARITHMETIC,tokens=tokens,cached_tokens=0,gpu_count=1,
                    decode_mode='plain',context=4096,requested_max_new=cap,prompt_tokens=e['prompt_tokens'],
                    request_start_monotonic=10.,request_end_monotonic=20.,
                    timing_rows=[dict(completed_monotonic=11+i*interval) for i in range(len(tokens))]))
                D.save(actual/'reset.json',dict(passed=True,cached_tokens=0,allocation_ids_preserved=True))

    def test_smoke_report_uses_real_exact_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);self.fixture(out,'smoke')
            row=D.summarize_bracket(out,'smoke',self.manifest)
            self.assertTrue(row['smoke_passed']);self.assertEqual(row['request_count'],12)
            self.assertEqual(row['requested_max_new'],64)
            path=out/'run/S0'/self.manifest['prompts'][-1]['prompt_id']/'result.json'
            bad=D.read(path);bad['tokens'][-1]+=1;D.save(path,bad)
            with self.assertRaisesRegex(ValueError,'token identity'):D.summarize_bracket(out,'smoke',self.manifest)

    def test_all60_actual_oracle_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);self.fixture(out)
            row=D.summarize_bracket(out,'resident',self.manifest)
            self.assertTrue(row['candidate_beats_all_controls'])
            self.assertEqual(row['request_count'],60)
            self.assertFalse(row['realistic_final_gate']['passed'])
            self.assertTrue(all(len(v['requests'])==12 for v in row['views']))
            self.assertTrue(all(r['submission100']['interval_count']==99 for v in row['views'] for r in v['requests'] if not r['early_end_before_100']))
            # Last token in the last view is checked, not merely a prefix/hash.
            path=out/'run/A2'/self.manifest['prompts'][-1]['prompt_id']/'result.json'
            bad=D.read(path);bad['tokens'][-1]+=1;D.save(path,bad)
            with self.assertRaisesRegex(ValueError,'token identity'):D.summarize_bracket(out,'resident',self.manifest)

    def test_boundary_and_reset_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);self.fixture(out)
            path=out/'run/B1/boundary.json';original=D.read(path)
            for key,value in (('selection_sha256','bad'),('hc','mapped'),('cache_cap','18GB'),('weight_uploads_during_switch',1),('model_loads',2),
                              ('allocation_ids_preserved',False),('context_extent',4096),('arena_descriptors_sha256','other')):
                D.save(path,dict(original,**{key:value}))
                with self.subTest(key=key),self.assertRaises(ValueError):D.summarize_bracket(out,'resident',self.manifest)
            D.save(path,original)
            path=out/'run/B1'/self.manifest['prompts'][0]['prompt_id']/'reset.json'
            D.save(path,dict(passed=True,cached_tokens=1,allocation_ids_preserved=True))
            with self.assertRaisesRegex(ValueError,'reset'):D.summarize_bracket(out,'resident',self.manifest)


class TeardownIntegrationTests(unittest.TestCase):
    def scenario(self, mutation=lambda row:None, *, live=False, fault=False, driver_live=False, foreign=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);proc=root/'proc';proc.mkdir();drain=root/'drain';drain.mkdir()
            out=root/'output';(out/'run/run').mkdir(parents=True)
            native=dict(passed=False,safe_to_exit=True,compute_started=True,device_executed=True,owner_cards=1,
                teardown=[dict(status='complete',safe_to_exit=True,idle_marker_complete=True,error='',exit_code=0,live_bytes=0,in_flight=0)])
            mutation(native);D.save(out/'run/run/receipt.json',native)
            with W.A.Admission('WSCREEN',out/'window.json',lambda:None,root=root/'lanes',drain_root=drain,proc=proc) as admission:
                admission.before_launch()
                owner=F.AdmissionTests().proc_owner(proc,42,'0000:23:00.0');admission.observe(dict(processes=[dict(pid=42)]))
                if not live:
                    import shutil
                    shutil.rmtree(owner)
                if foreign:F.AdmissionTests().proc_owner(proc,44,'0000:43:00.0')
                child=SimpleNamespace(pid=43,poll=lambda:None if driver_live else 1)
                def check():
                    if fault:raise ValueError('new GPU fault')
                bad=live or fault or driver_live or foreign or native['teardown'][0]['in_flight'] or not native['safe_to_exit']
                if bad:
                    with self.assertRaises(ValueError):finish_model_owner(child,out,admission,check)
                    self.assertFalse(admission.drained)
                else:
                    row=finish_model_owner(child,out,admission,check)
                    self.assertTrue(row['passed']);self.assertFalse(row['experiment_passed'])
                    self.assertTrue(admission.drained);self.assertFalse(admission.record['passed'])
                self.assertEqual((root/'lanes/active-lane-A.json').exists(),bool(bad))

    def test_postcompute_error_cleanly_drained(self):self.scenario()
    def test_live_native_retained(self):self.scenario(live=True)
    def test_live_driver_retained(self):self.scenario(driver_live=True)
    def test_new_fault_retained(self):self.scenario(fault=True)
    def test_foreign_owner_retained(self):self.scenario(foreign=True)
    def test_inflight_retained(self):self.scenario(lambda r:r['teardown'][0].update(in_flight=1))
    def test_missing_safe_exit_retained(self):self.scenario(lambda r:r.update(safe_to_exit=False))

if __name__=='__main__':unittest.main()
