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

import audit_sparse_replication_v1 as sparse
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


class ReplicationAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sparse-replication-audit-tests-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.packet=CONTEXT.parents[1]/'data/2026-10-07-sparse-state-replication'
        # Deliberately remove originating-host paths in the COPY. Every audit
        # regression therefore exercises portable evidence, even on the lab host.
        original_packet=cls.packet;cls.packet=Path(cls.temp.name)/'portable-packet'
        shutil.copytree(original_packet,cls.packet)
        budget=read(cls.packet/'budget-receipt.json')
        budget['tokenizer_path']=str(Path(cls.temp.name)/'missing-tokenizer.json')
        budget['tokenizer_python']=str(Path(cls.temp.name)/'missing-python')
        (cls.packet/'budget-receipt.json').write_text(json.dumps(budget))
        plan=read(cls.packet/'plan.json');plan['files_sha256']['budget-receipt.json']=sha(cls.packet/'budget-receipt.json')
        (cls.packet/'plan.json').write_text(json.dumps(plan))
        cls.plan,cls.tasks=sparse.load_packet(cls.packet)
        cls.base=Path(cls.temp.name)/'base'
        fixture_script = """\
# Stub fixtures ONLY: portable independent source/evidence validation replaces
# host tokenizer recomputation. Production prepare/live validation is untouched.
import importlib,sys
from pathlib import Path
from unittest.mock import patch
context,folder,auditor_name,packet,out=sys.argv[1:]
sys.path.insert(0,context)
auditor=importlib.import_module(auditor_name)
sys.path.insert(0,str(Path(context)/folder))
import runner
def portable_stub_bundle(packet):
    plan,tasks=auditor.load_packet(packet)
    assert plan['wrapper_source_sha256']==runner.source_hashes()
    assert plan['engine_source_sha256']==runner.verify_engine()['source_sha256']
    return {'plan':plan,'tasks':tasks,'budget':auditor.read(Path(packet)/'budget-receipt.json')}
with patch.object(runner,'validate_packet',side_effect=portable_stub_bundle):
    runner.execute(packet,out,stub=True)
"""
        subprocess.run([sys.executable,'-c',fixture_script,str(CONTEXT),'sparse_replication_v1',sparse.__name__,
                        str(cls.packet),str(cls.base/'diagnostic')],check=True,capture_output=True,
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
            pairs.setdefault(item['case_id'],[]).append(row)
        summary.update(trials=rows,observed_trials=count,completed_trials=sum(r['status']=='completed' for r in rows),
                       failed_trials=sum(r['status']=='failed' for r in rows),infrastructure_abort=abort,
                       infrastructure_error='CPU fixture' if abort else None,
                       status='failed' if abort else 'completed' if count==4 else 'running',
                       paired_quality={k:len(v)==2 and all(r['quality_passed'] for r in v) for k,v in pairs.items()})
        self.write(path,summary)

    def test_fixture_and_audit_work_without_originating_host_tokenizer_paths(self):
        budget=read(self.packet/'budget-receipt.json')
        self.assertFalse(Path(budget['tokenizer_path']).exists())
        self.assertFalse(Path(budget['tokenizer_python']).exists())
        result=sparse.audit(self.root,self.packet)
        self.assertEqual(result['completed_trials'],4)
        self.assertEqual(result['measurement_kind'],'stub')
        self.assertTrue(all(row['reference_checks_passed'] for row in result['trials']))

    def test_complete_stub_is_wiring_only_with_all_native_costs(self):
        result=sparse.audit(self.root,self.packet)
        self.assertEqual(result['completed_trials'],4)
        self.assertEqual(result['measurement_kind'],'stub')
        for row in result['trials']:
            self.assertTrue(row['reference_checks_passed']);self.assertFalse(row['quality_passed'])
            self.assertEqual(row['native_audit']['correct'],24)
            self.assertEqual(row['phase_costs']['steady']['calls'],16)
            initial=8
            self.assertEqual(row['phase_costs']['initialization']['calls'],initial)
            self.assertEqual(row['phase_costs']['total']['calls'],initial+17)
            self.assertIsNone(row['phase_costs']['total']['completion_tokens'])
        for pair in result['pairs'].values():
            self.assertFalse(pair['cold_comparison_eligible']);self.assertIsNone(pair['elapsed_reduction_percent'])
            self.assertFalse(pair['original_task_repeat_signal']);self.assertFalse(pair['speed_gate_passed'])

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
        self.assertFalse(result['pairs']['sparse-n128-seed97-dispatch']['cold_comparison_eligible'])
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

    def test_repeat_and_transfer_are_separate_cold_quality_scoped_signals(self):
        rows=[]
        for case in ('sparse-n128-seed83','sparse-n128-seed97-dispatch'):
            rows.extend({'case_id':case,'arm':arm,'quality_passed':True,'cold_cost_interpretation':True,
                         'total_trial_wall_seconds':seconds} for arm,seconds in [('archive',100),('quoted',89)])
        pairs=sparse.descriptive_pairs(rows,'model')
        repeat=pairs['sparse-n128-seed83'];transfer=pairs['sparse-n128-seed97-dispatch']
        self.assertTrue(repeat['original_task_repeat_signal']);self.assertFalse(repeat['new_case_transfer_signal'])
        self.assertTrue(transfer['new_case_transfer_signal']);self.assertFalse(transfer['original_task_repeat_signal'])
        self.assertAlmostEqual(repeat['elapsed_reduction_percent'],11)
        self.assertFalse(repeat['speed_gate_passed']);self.assertFalse(transfer['holdout_admitted'])
        for key in ('quality_passed','cold_cost_interpretation'):
            changed=copy.deepcopy(rows);changed[0][key]=False
            pairs=sparse.descriptive_pairs(changed,'model')
            self.assertIsNone(pairs['sparse-n128-seed83']['elapsed_reduction_percent'])
            self.assertTrue(pairs['sparse-n128-seed97-dispatch']['new_case_transfer_signal'])
        self.assertIsNone(sparse.descriptive_pairs(rows,'stub')['sparse-n128-seed83']['elapsed_reduction_percent'])
        rows[1]['total_trial_wall_seconds']=90.01
        self.assertFalse(sparse.descriptive_pairs(rows,'model')['sparse-n128-seed83']['original_task_repeat_signal'])

    def test_source_parser_checks_every_event_and_honest_historical_coverage(self):
        for case,task in self.tasks.items():
            row=next(row for row in self.plan['trials'] if row['case_id']==case)
            document=read(self.packet/row['document_path'])
            states,events,answers,coverage=sparse.source_reference(document,row['style'])
            self.assertEqual(len(states),24);self.assertEqual(sum(map(len,events)),176)
            self.assertEqual(answers,task['oracle']['answers']);self.assertEqual(coverage['historical_questions'],16)
            self.assertEqual(coverage['differs_from_final'],2)
            self.assertEqual(coverage,self.plan['historical_coverage'][case])
            changed=copy.deepcopy(document);changed['batches'][8]['text']+='\nAn unrecognized posting adds 7 to unitaa10.'
            with self.assertRaisesRegex(ValueError,'unrecognized source'):sparse.source_reference(changed,row['style'])
            changed=copy.deepcopy(document);changed['questions'][1]['text']=changed['questions'][1]['text'].replace('batch 9?','batch 10?')
            with self.assertRaisesRegex(ValueError,'selection/time'):sparse.source_reference(changed,row['style'])

    def test_frozen_report_bytes_and_coverage_cannot_be_rewritten(self):
        packet=Path(self.temp.name)/'packet';shutil.copytree(self.packet,packet)
        path=packet/'sparse-n128-seed83-document.json';path.write_bytes(path.read_bytes()+b'\n')
        plan=read(packet/'plan.json');plan['files_sha256'][path.name]=sha(path);self.write(packet/'plan.json',plan)
        with self.assertRaisesRegex(ValueError,'original report bytes'):sparse.load_packet(packet)
        shutil.rmtree(packet);shutil.copytree(self.packet,packet)
        plan=read(packet/'plan.json');plan['historical_coverage']['sparse-n128-seed83']['differs_from_final']=16
        self.write(packet/'plan.json',plan)
        with self.assertRaisesRegex(ValueError,'historical question coverage'):sparse.load_packet(packet)

    def test_dispatch_private_answer_rewrite_fails_source_replay(self):
        packet=Path(self.temp.name)/'packet';shutil.copytree(self.packet,packet)
        plan=read(packet/'plan.json');row=plan['trials'][2];path=packet/row['task_path']
        task=read(path);task['oracle']['answers']['history-0']+=1
        task['task_sha256']=sparse.digest({key:value for key,value in task.items() if key!='task_sha256'})
        self.write(path,task);plan['files_sha256'][path.name]=sha(path)
        for item in plan['trials']:
            if item['case_id']==row['case_id']:item['task_sha256']=task['task_sha256']
        self.write(packet/'plan.json',plan)
        with self.assertRaisesRegex(ValueError,'private answers disagree'):sparse.load_packet(packet)

    def test_dispatch_reference_cannot_hide_an_accepted_event_semantic_error(self):
        item=self.plan['trials'][2];task=self.tasks[item['case_id']]
        native=self.replace_native(2,NetZeroStub(task));self.update_summary()
        self.assertEqual(native['score']['correct'],24);self.assertTrue(native['all_checkpoint_states_exact'])
        result=sparse.audit(self.root,self.packet)
        self.assertFalse(result['trials'][2]['reference_checks_passed'])
        self.assertEqual(result['trials'][2]['native_audit']['accepted_events']['extra_events'],2)


if __name__=='__main__':unittest.main()
