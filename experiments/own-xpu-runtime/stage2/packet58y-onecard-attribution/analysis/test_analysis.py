"""Synthetic-only analysis tests. No device process or real receipt is modified."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import analyze as A
import suite_driver as D
from attribution_schema import PHASES,CAUSES,CLASSES,COUNTERS


def trace_row(position,index,token):
    host=dict(prepare=.5,enqueue=2.,cache_boundary=1.,cache_plan=1.,readbacks=.1,cache_after=.4)
    waits={k:0. for k in CAUSES};waits.update(compute_including_zero_copy_miss=20.,table_publication=.5,readbacks=1.,input_upload=.1)
    return dict(schema='packet58y.token.v1',profiling=False,extra_device_waits=0,
        device_class_ms={n:None for n in CLASSES},zero_copy_miss_stall_ms=None,
        host_exclusive_ms=host,host_wait_ms=waits,host_wait_calls={n:0 for n in CAUSES},
        residual_ms=30-sum(host.values())-sum(waits.values()),wall_ms=30.,enqueue_class_ms=[0.]*10,class_submissions=[0]*10,
        **{n:0 for n in COUNTERS if n not in ('hits','misses')},hits=400,misses=80,fill_pending_end=False,
        position=position,generated_index=index,token_id=token)


class Bounds(unittest.TestCase):
    def prompts(self):
        return [dict(prompt_class='class'+str(i//2),rate=25.,interval_ms=3960.,selected=[trace_row(n,n,0) for n in range(99)]) for i in range(12)]

    def test_class_balanced_metric_not_all_prompt_mean(self):
        rows=self.prompts();rows[0]['rate']=1000
        result=A.balanced(rows,'rate')
        self.assertEqual(result['median'],25)
        self.assertEqual(result['class_medians']['class0'],512.5)

    def test_gate_kills_small_bound_and_never_promotes_upper_bound(self):
        result={row['lever']:row for row in A.rank_levers(self.prompts())}
        self.assertEqual(result['planning']['decision'],'kill_below_3pct')
        self.assertAlmostEqual(result['planning']['perfect_removal_bound_gain_pct'],100*(40/39-1))
        self.assertEqual(result['enqueue']['decision'],'needs_causal_test')
        self.assertTrue(all(not row['passes_implementation_gate'] for row in result.values()))

    def test_bad_duration_or_class_coverage_refuses(self):
        rows=self.prompts();rows[0]['interval_ms']=1
        with self.assertRaises(ValueError):A.rank_levers(rows)
        with self.assertRaises(ValueError):A.balanced(self.prompts()[:4],'rate')

    def test_byte_count_alone_cannot_rank_miss_path(self):
        ranking=A.rank_levers(self.prompts())
        assessment=A.describe_top_items(ranking,dict(decision='below_3pct_priority_gate',passes_3pct_screen_gate=False))
        self.assertEqual(assessment['larger_cache_and_miss_path_both_remain_top'],'not established')
        self.assertIn('unknown',assessment['miss_path'])

    def test_exact_three_percent_bound_is_not_killed(self):
        rows=self.prompts()
        for p in rows:
            p['interval_ms']=4120
            for row in p['selected']:row['host_exclusive_ms']['enqueue']=0
            p['selected'][0]['host_exclusive_ms']['enqueue']=120
        result={r['lever']:r for r in A.rank_levers(rows)}
        self.assertEqual(result['enqueue']['decision'],'needs_causal_test')
        self.assertEqual(result['enqueue']['perfect_removal_bound_gain_pct'],3)

    def test_capacity_exact_boundary(self):
        rates=dict(A0=90,A1=100,A2=103,B0=106.09,B1=106.09)
        class FakeEvidence:
            def raw(self,path):return b'{}'
            def js(self,path):return dict(cache_maintenance='overlap',cache_cap='max' if path.parent.name.startswith('B') else '18GB',
                cache_allocation_bytes=21_552_729_600,cache_started_empty=True,selection_sha256=D.digest('attrib'))
        def summary(root,stage,manifest,label,cap):
            return dict(class_balanced_tok_s_1_100_intervals_after_ttft=dict(median=rates[label]),requests=[0]*12)
        with patch.object(A,'window',return_value=dict(boot_id='test')),patch.object(D,'summarize',side_effect=summary):
            row=A.analyze_capacity(FakeEvidence(),{},'test')
        self.assertEqual(row['control_drift_pct'],3)
        self.assertEqual(row['measured_screen_gain_pct'],3)
        self.assertTrue(row['passes_3pct_screen_gate'])


class EndToEnd(unittest.TestCase):
    def make_window(self,root,packet,attrib=False):
        from test_bracket import SummaryTests
        root.mkdir(parents=True);helper=SummaryTests();helper.manifest=D.oracle_inputs();helper.fixture(root/'run') if (root/'run').mkdir() is None else None
        native=root/'run/run'
        if attrib:
            (native/'B0').rename(native/'D0')
            for entry in helper.manifest['prompts']:
                folder=native/'D0'/entry['prompt_id'];result=D.read(folder/'result.json')
                rows=[]
                for position in range(result['prompt_tokens']-1+len(result['tokens'])):
                    index=max(0,position-result['prompt_tokens']+2)
                    rows.append(trace_row(position,index,result['tokens'][index-1] if index else 0))
                (folder/'attribution.jsonl').write_text('\n'.join(map(json.dumps,rows))+'\n')
            summary=D.summarize_bracket(root/'run','attrib',helper.manifest)
            D.save(root/'run/summary.json',summary)
        else:
            for label,cap in [('A0','18GB'),('B0','max'),('A1','18GB'),('B1','max'),('A2','18GB')]:
                f=native/label/'boundary.json';row=D.read(f);row.update(cache_maintenance='overlap',cache_cap=cap,cache_allocation_bytes=21_552_729_600,cache_started_empty=True);D.save(f,row)
        proof=dict(passed=True,device_executed=True,child_still_running=False,stop_reasons=[],card=0,gpu_count=1,context=4096,window='WSCREEN',
            started_utc_ns=1000,finished_utc_ns=1010,
            build_receipt_sha256=A.hashlib.sha256((packet/'build-receipt.json').read_bytes()).hexdigest(),boot_id='synthetic-test-boot',
            lane_admission=dict(passed=True,card=0,scope='whole-host',timing_claim_eligible=False,reservation=dict(boot_id='synthetic-test-boot')),
            native_files={str(f.relative_to(root)):A.hashlib.sha256(f.read_bytes()).hexdigest() for f in (root/'run').rglob('*') if f.is_file()})
        D.save(root/'window.json',proof)
        return proof

    def fixture(self,tmp):
        packet=tmp/'packet58y';packet.mkdir();(packet/'build-receipt.json').write_text('{}')
        build_hash=A.hashlib.sha256((packet/'build-receipt.json').read_bytes()).hexdigest()
        D.save(packet/'READY-FOR-DEVICE.json',dict(build_receipt_sha256=build_hash))
        parent=tmp/'packet58x-cache-capacity';parent.mkdir();(parent/'build-receipt.json').write_text('{}')
        self.make_window(parent/'evidence/card0-capacity-a/max/WSCREEN',parent)
        pins={};stamp=100
        for arm in ('smoke','max'):
            root=parent/'evidence/card0-capacity-a'/arm
            for stage in ('K1a','K1b','WSCREEN'):
                f=root/stage/'window.json';f.parent.mkdir(parents=True,exist_ok=True)
                row=D.read(f) if f.exists() else dict(passed=True,device_executed=True,child_still_running=False,stop_reasons=[],
                    boot_id='synthetic-test-boot',build_receipt_sha256=build_hash)
                row.update(started_utc_ns=stamp,finished_utc_ns=stamp+10);stamp+=20;D.save(f,row)
                pins[str(f.relative_to(A.ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
            f=root/'queue.json';D.save(f,dict(passed=True,completed=['K1a','K1b','WSCREEN'],running=None))
            pins[str(f.relative_to(A.ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
        run=packet/'evidence/card0-attribution-a/attrib'
        self.make_window(run/'WSCREEN',packet,attrib=True)
        D.save(run/'queue.json',dict(passed=True,completed=['K1a','K1b','WSCREEN'],running=None,batch_admission=dict(
            passed=True,same_hold_required=True,standalone_hold_allowed=False,boot_id='synthetic-test-boot',predecessor_receipts=pins,
            pause=dict(device=1,inode=1,mtime_ns=90,ctime_ns=90))))
        return packet,run

    def test_full_evidence_path_and_tampered_trace(self):
        import window as W
        # Place fixtures under repository analysis scratch so source-pin paths
        # are exercised, not bypassed. These files are removed by TemporaryDirectory.
        with tempfile.TemporaryDirectory(prefix='synthetic-analysis-',dir=Path(__file__).parent) as tmp:
            packet,run=self.fixture(Path(tmp))
            with patch.object(A,'P',packet),patch.object(W,'build_gate',return_value={'synthetic_cpu_seal':True}):
                result=A.analyze()
                self.assertEqual(result['status'],'complete_diagnostic')
                self.assertEqual(result['measured_split']['tokens'],1188)
                self.assertFalse(result['implementation_gate_passed'])
                self.assertFalse(result['submission_eligible'])
                self.assertTrue(result['larger_cache']['passes_3pct_screen_gate'])
                self.assertEqual(result['primary_metric']['median'],result['primary_metric']['all_prompt_median'])
                self.assertTrue(result['per_prompt'][0]['cold_first_request'])
                trace=next((run/'WSCREEN/run/run/D0').glob('*/attribution.jsonl'))
                trace.write_text(trace.read_text().splitlines()[0]+'\n')
                with self.assertRaisesRegex(ValueError,'changed evidence'):A.analyze()

    def test_missing_data_returns_pending_without_ranking(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp,patch.object(A,'P',Path(tmp)):
            row=A.analyze();self.assertEqual(row['status'],'pending_device_evidence');self.assertIsNone(row['ranking'])

    def test_closure_refuses_escape(self):
        e=A.Evidence()
        with self.assertRaisesRegex(ValueError,'unsafe'):e.verify_files(Path('/tmp'),{'../escape':'0'*64})

    def test_empty_predecessor_coverage_refused(self):
        with self.assertRaisesRegex(ValueError,'coverage'):A.verify_predecessors(A.Evidence(),dict(predecessor_receipts={}))

    def test_refusal_replaces_stale_success_markdown(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp,patch.object(A,'P',Path(tmp)):
            out=Path(tmp)/'analysis/report.json';out.parent.mkdir();out.with_suffix('.md').write_text('Old successful ranking')
            with patch.object(A,'analyze',side_effect=ValueError('synthetic invalid receipt')):
                self.assertEqual(A.main(['--output',str(out)]),1)
            self.assertIn('evidence refused',out.with_suffix('.md').read_text())
            self.assertNotIn('Old successful',out.with_suffix('.md').read_text())

if __name__=='__main__':unittest.main()
