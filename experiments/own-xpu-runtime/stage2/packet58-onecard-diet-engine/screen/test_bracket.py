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


class SummaryTests(unittest.TestCase):
    """Replay actual 60-request checker with synthetic native receipts in scratch."""
    @classmethod
    def setUpClass(cls):cls.manifest=D.oracle_inputs()

    def fixture(self,out,candidate="resident"):
        cap=64 if candidate=="smoke" else 128
        run=out/'run';run.mkdir()
        native=dict(passed=True,safe_to_exit=True,device_executed=True,owner_cards=1,
            cpu_affinity=[0,1,2,3,16,17,18,19],observed_nice=0,native_nice=0,
            teardown=[dict(safe_to_exit=True,idle_marker_complete=True,exit_code=0,live_bytes=0,in_flight=0)])
        D.save(run/'receipt.json',native)
        for label,view,gateup in V.bracket(candidate):
            folder=run/label;folder.mkdir()
            D.save(folder/'boundary.json',dict(passed=True,cache_maintenance=V.DEFAULT_MAINTENANCE,cache_cap=view,hc="p60fusion",lookups='resident',wait_policy='spin',bracket_arm=V.FOREGROUND,foreground_io='kernel',cache_allocation_bytes=V.ALLOCATION_BYTES,cache_usable_bytes=V.USABLE[view],cache_started_empty=True,selection_sha256=V.digest(view),allocation_ids_preserved=True,
                weight_uploads_during_switch=0,model_loads=1,context_extent=32,arena_descriptors_sha256='a'*64,weight_descriptors_sha256='b'*64,
                expert_gateup=gateup,expert_diet_sites=47 if gateup=='diet' else 0,expert_production_sites=0 if gateup=='diet' else 47))
            D.save(folder/'lookup-backing.json',dict(resident=True,copies=dict(enabled=True,bytes=29321610240,tensors=[dict(source_sha256='a'*64,resident_sha256='a'*64)])))
            for e in self.manifest['prompts']:
                actual=folder/e['prompt_id'];actual.mkdir()
                tokens=D.CHECK.token_record(D.ORACLE/'results'/e['prompt_id'])[:cap]
                interval=.04 if gateup=='production' else .039   # synthetic rates: B faster than A; never device data
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
            for key,value in (('selection_sha256','bad'),('selection_sha256','mapped'),('cache_cap','18GB'),('cache_allocation_bytes',21552729600),('weight_uploads_during_switch',1),('model_loads',2),
                              ('allocation_ids_preserved',False),('context_extent',4096),('arena_descriptors_sha256','other')):
                D.save(path,dict(original,**{key:value}))
                with self.subTest(key=key),self.assertRaises(ValueError):D.summarize_bracket(out,'resident',self.manifest)
            D.save(path,original)
            path=out/'run/B1'/self.manifest['prompts'][0]['prompt_id']/'reset.json'
            D.save(path,dict(passed=True,cached_tokens=1,allocation_ids_preserved=True))
            with self.assertRaisesRegex(ValueError,'reset'):D.summarize_bracket(out,'resident',self.manifest)


class GateUpBoundaryTests(unittest.TestCase):
    """verify_lookup_views (device path, before the summary) enforces the per-view gate/up identity."""
    @classmethod
    def setUpClass(cls):cls.manifest=D.oracle_inputs()

    def fixture(self,out):
        SummaryTests.fixture(self,out)
        D.save(out/'run/receipt.json',dict(D.read(out/'run/receipt.json'),lookup_residency=dict(enabled=True,bytes=29321610240,tensors=[dict(source_sha256='a'*64,resident_sha256='a'*64)])))
        for label,_,_ in V.bracket('resident'):
            for e in self.manifest['prompts']:
                root=out/'run'/label/e['prompt_id']
                D.save(root/'owner-cpu.json',dict(cpu_seconds=1.0,wall_seconds=2.0,one_core_percent=50.0))
                (root/'timings.jsonl').write_text('{"wall_ms":1.0}\n');(root/'prefill-timings.jsonl').write_text('{"wall_ms":1.0}\n')

    def test_gateup_boundary_mutations_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);self.fixture(out)
            with patch.object(D,'oracle_inputs',return_value=self.manifest):
                from resident_receipt import check_lookups
                with patch('resident_receipt.check_lookups',lambda *a,**k:None):
                    D.verify_lookup_views(out,'resident')
                    path=out/'run/B1/boundary.json';original=D.read(path)
                    for key,value in (('expert_gateup','production'),('expert_diet_sites',46),('expert_diet_sites',48),('expert_diet_sites',0),('expert_production_sites',3),('cache_cap','max'),('cache_usable_bytes',21552729600)):
                        D.save(path,dict(original,**{key:value}))
                        with self.subTest(key=key),self.assertRaises(ValueError):D.verify_lookup_views(out,'resident')
                    D.save(path,original)
                    path=out/'run/A1/boundary.json';original=D.read(path)
                    for key,value in (('expert_gateup','diet'),('expert_diet_sites',1)):
                        D.save(path,dict(original,**{key:value}))
                        with self.subTest(key=key),self.assertRaises(ValueError):D.verify_lookup_views(out,'resident')


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
