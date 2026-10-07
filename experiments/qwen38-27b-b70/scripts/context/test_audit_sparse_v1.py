"""CPU-only sparse native audit fixtures; no model or device calls."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import audit_sparse_v1 as sparse
from audit_semantic_v1 import read,sha

CONTEXT=Path(__file__).parent
sys.path.insert(0,str(CONTEXT/'semantic_v1'))
import live as semantic_live


class MalformedStub:
    kind='stub'
    def __call__(self,*args):return '{',{}


class InfrastructureStub:
    kind='stub'
    def __call__(self,*args):raise semantic_live.InfrastructureError('CPU fixture transport failure')


class NetZeroStub(semantic_live.StubClient):
    def __call__(self,messages,phase,batch_id):
        text,usage=super().__call__(messages,phase,batch_id)
        reply=json.loads(text)
        if phase=='quoted' and batch_id==2:
            first,last=reply['events'][0],reply['events'][-1]
            base={'counter':first['counter'],'amount':first['amount'],'quote':last['quote']}
            reply['events'] += [{**base,'op':'add'},{**base,'op':'sub'}]
        return json.dumps(reply),usage


class SparseAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sparse-audit-tests-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.packet=CONTEXT.parents[1]/'data/2026-10-07-sparse-state-development'
        cls.plan,cls.tasks=sparse.load_packet(cls.packet)
        cls.base=Path(cls.temp.name)/'base'
        subprocess.run([sys.executable,str(CONTEXT/'sparse_v1/runner.py'),'--packet',str(cls.packet),
                        '--out',str(cls.base/'diagnostic'),'--stub'],check=True,capture_output=True,
                       env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=120)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'output';shutil.copytree(self.base,self.root)
        self.diag=self.root/'diagnostic'

    def write(self,path,value):path.write_text(json.dumps(value))

    def replace_native(self,index,client,reference_checks=False):
        item=self.plan['trials'][index];outer_path=self.diag/item['result_path'];outer=read(outer_path)
        native_path=self.diag/item['native_result_path'];shutil.rmtree(native_path.parent)
        try:semantic_live.run_trial(self.tasks[item['case_id']],item['arm'],native_path.parent,client)
        except semantic_live.InfrastructureError:pass
        native=read(native_path)
        calls=[json.loads(line) for line in (native_path.parent/'calls.jsonl').read_text().splitlines()]
        costs=sparse.phase_costs(calls,self.tasks[item['case_id']]['generated_provenance']['initialization_batches'])
        outer.update(status=native['status'],reference_checks_passed=reference_checks,quality_passed=False,
                     phase_costs=costs,total_trial_wall_seconds=native['wall_seconds'],
                     non_call_overhead_seconds=native['wall_seconds']-costs['total']['client_call_seconds'],
                     native_sha256=sha(native_path),native_artifacts=native['artifacts'])
        self.write(outer_path,outer)
        return native

    def update_summary(self,count=4,abort=False):
        path=self.diag/'summary.json';summary=read(path);rows=[];pairs={}
        for item in self.plan['trials'][:count]:
            result=read(self.diag/item['result_path']);row={**item,'status':result['status'],'quality_passed':result['quality_passed']};rows.append(row)
            pairs.setdefault(str(item['counter_count']),[]).append(row)
        summary.update(trials=rows,observed_trials=count,completed_trials=sum(r['status']=='completed' for r in rows),
                       failed_trials=sum(r['status']=='failed' for r in rows),infrastructure_abort=abort,
                       infrastructure_error='CPU fixture' if abort else None,
                       status='failed' if abort else 'completed' if count==4 else 'running',
                       paired_quality={k:len(v)==2 and all(r['quality_passed'] for r in v) for k,v in pairs.items()})
        self.write(path,summary)

    def test_complete_stub_is_wiring_only_with_all_native_costs(self):
        result=sparse.audit(self.root,self.packet)
        self.assertEqual(result['completed_trials'],4)
        self.assertEqual(result['measurement_kind'],'stub')
        for row in result['trials']:
            self.assertTrue(row['reference_checks_passed']);self.assertFalse(row['quality_passed'])
            self.assertEqual(row['native_audit']['correct'],24)
            self.assertEqual(row['phase_costs']['steady']['calls'],16)
            initial=1 if row['counter_count']==8 else 8
            self.assertEqual(row['phase_costs']['initialization']['calls'],initial)
            self.assertEqual(row['phase_costs']['total']['calls'],initial+17)
            self.assertIsNone(row['phase_costs']['total']['completion_tokens'])
        for pair in result['pairs'].values():
            self.assertFalse(pair['cold_comparison_eligible']);self.assertIsNone(pair['elapsed_reduction_percent'])
            self.assertFalse(pair['replication_signal']);self.assertFalse(pair['speed_gate_passed'])

    def test_phase_cost_or_stub_quality_rewrite_is_rejected(self):
        path=self.diag/self.plan['trials'][0]['result_path'];original=read(path)
        changed=copy.deepcopy(original);changed['phase_costs']['initialization']['calls']+=1;self.write(path,changed)
        with self.assertRaisesRegex(ValueError,'phase cost'):sparse.audit(self.root,self.packet)
        changed=copy.deepcopy(original);changed['quality_passed']=True;self.write(path,changed)
        with self.assertRaisesRegex(ValueError,'quality/cold'):sparse.audit(self.root,self.packet)

    def test_reordered_output_matrix_and_native_binding_are_rejected(self):
        path=self.diag/'plan.json';changed=read(path);changed['trials'].reverse();self.write(path,changed)
        with self.assertRaisesRegex(ValueError,'output plan'):sparse.audit(self.root,self.packet)
        self.write(path,self.plan)
        path=self.diag/self.plan['trials'][0]['result_path'];changed=read(path);changed['native_sha256']='0'*64;self.write(path,changed)
        with self.assertRaisesRegex(ValueError,'native binding'):sparse.audit(self.root,self.packet)

    def test_model_label_requires_real_bound_identity(self):
        path=self.diag/'summary.json';summary=read(path);summary['measurement_kind']='model';self.write(path,summary)
        with self.assertRaisesRegex(ValueError,'bound server identity'):sparse.audit(self.root,self.packet)

    def test_unstarted_and_native_without_outer_receipt_remain_visible(self):
        last=self.plan['trials'][-1];outer=self.diag/last['result_path'];outer.unlink();self.update_summary(3)
        result=sparse.audit(self.root,self.packet)
        self.assertEqual(result['incomplete_trials'],1);self.assertEqual(len(result['trials']),4)
        self.assertEqual(result['trials'][-1]['native_status'],'completed')
        self.assertFalse(result['pairs']['128']['cold_comparison_eligible'])
        shutil.rmtree(outer.parent)
        result=sparse.audit(self.root,self.packet)
        self.assertEqual(result['unstarted_trials'],1);self.assertEqual(len(result['trials']),4)

    def test_bounded_failure_retains_all_four_planned_rows(self):
        self.replace_native(0,MalformedStub());self.update_summary()
        result=sparse.audit(self.root,self.packet)
        self.assertEqual(result['completed_trials'],3);self.assertEqual(result['failed_trials'],1)
        failed=result['trials'][0]
        self.assertFalse(failed['quality_passed']);self.assertEqual(failed['native_audit']['correct'],0)
        self.assertFalse(failed['native_audit']['source_delivery_complete'])
        self.assertEqual(failed['phase_costs']['total']['calls'],3)

    def test_infrastructure_failure_preserves_failed_row_and_unstarted_tail(self):
        self.replace_native(0,InfrastructureStub())
        for item in self.plan['trials'][1:]:shutil.rmtree((self.diag/item['result_path']).parent)
        self.update_summary(1,abort=True)
        result=sparse.audit(self.root,self.packet)
        self.assertTrue(result['infrastructure_abort']);self.assertEqual(result['failed_trials'],1)
        self.assertEqual(result['unstarted_trials'],3);self.assertEqual(len(result['trials']),4)

    def test_net_zero_extra_events_fail_reference_quality_despite_all_answers_and_states(self):
        item=self.plan['trials'][1]
        native=self.replace_native(1,NetZeroStub(self.tasks[item['case_id']]))
        self.assertTrue(native['all_checkpoint_states_exact']);self.assertEqual(native['score']['correct'],24)
        self.update_summary();result=sparse.audit(self.root,self.packet);row=result['trials'][1]
        self.assertFalse(row['reference_checks_passed'])
        self.assertEqual(row['native_audit']['accepted_events']['extra_events'],2)
        self.assertFalse(row['native_audit']['all_accepted_events_exact'])

    def test_threshold_signal_requires_two_quality_clean_cold_model_rows(self):
        rows=[{'counter_count':128,'arm':arm,'quality_passed':True,'cold_cost_interpretation':True,
               'total_trial_wall_seconds':seconds} for arm,seconds in [('archive',100),('quoted',89)]]
        pair=sparse.descriptive_pairs(rows,'model')['128']
        self.assertTrue(pair['replication_signal']);self.assertAlmostEqual(pair['elapsed_reduction_percent'],11)
        self.assertFalse(pair['speed_gate_passed']);self.assertFalse(pair['holdout_admitted'])
        for key in ('quality_passed','cold_cost_interpretation'):
            changed=copy.deepcopy(rows);changed[0][key]=False
            pair=sparse.descriptive_pairs(changed,'model')['128']
            self.assertFalse(pair['replication_signal']);self.assertIsNone(pair['elapsed_reduction_percent'])
        self.assertIsNone(sparse.descriptive_pairs(rows,'stub')['128']['elapsed_reduction_percent'])


if __name__=='__main__':unittest.main()
