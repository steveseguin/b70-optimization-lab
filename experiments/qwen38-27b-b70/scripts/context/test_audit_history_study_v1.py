"""CPU-only native fixtures and adversarial audit checks; never model evidence."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import audit_history_study_v1 as audit


class HistoryStudyAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='history-study-audit-');cls.addClassCleanup(cls.temp.cleanup)
        cls.base=Path(cls.temp.name);cls.packet=cls.base/'packet';cls.results=cls.base/'results'
        script=r'''
import json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1]);import runner
packet,out=map(Path,sys.argv[2:]);tokenizer=packet.parent/'fake-tokenizer.json';tokenizer.write_text('{}')
def budget(packet,trials,tokenizer,python):
 rows=[]
 for item in trials:
  phases={}
  for phase,n in [('initialization',1),('steady',11),('answer',22 if item['retrieval_mode']=='history' else 13)]:
   phases[phase]={'calls':n,'max_reference_prompt_bytes':100,'max_reference_response_bytes':100,
      'max_reference_response_tokens':100,'max_prompt_bytes_with_ascii_memory_allowance':7000}
  rows.append({**{k:item[k] for k in ('case_id','condition','arm','retrieval_mode','task_sha256')},'phases':phases})
 return {'schema':'history-study-budget.v1','measurement_kind':'cpu-oracle-wiring-budget-check',
  'tokenizer_path':str(tokenizer),'tokenizer_sha256':runner.sha(tokenizer),'tokenizers_version':'CPU-test-fixture',
  'engine_source_sha256':runner.verify_engine()['source_sha256'],'trials':rows,
  'all_reference_prompts_fit':True,'all_reference_emissions_fit':True}
with patch.object(runner,'budget_check',side_effect=budget):
 runner.prepare(packet,tokenizer,sys.executable)
 runner.execute(packet,out,stub=True)
'''
        subprocess.run([sys.executable,'-B','-c',script,str(audit.HERE/'history_study_v1'),str(cls.packet),str(cls.results)],
            check=True,capture_output=True,text=True,timeout=120,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        # Portable auditor must not require the tokenizer executable or input.
        budget=audit.read(cls.packet/'budget-receipt.json');budget['tokenizer_path']='/missing/tokenizer'
        budget['tokenizer_python']='/missing/python';cls.write(cls.packet/'budget-receipt.json',budget)
        plan=audit.read(cls.packet/'plan.json');plan['files_sha256']['budget-receipt.json']=audit.sha(cls.packet/'budget-receipt.json')
        cls.write(cls.packet/'plan.json',plan);cls.write(cls.results/'plan.json',plan)
        cls.plan,cls.tasks=audit.load_packet(cls.packet)

    @staticmethod
    def write(path,value):path.write_text(json.dumps(value))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name)/'output';shutil.copytree(self.results,self.out)

    def replace(self,index,behavior):
        item=self.plan['trials'][index];native=self.out/item['native_result_path'];shutil.rmtree(native.parent)
        script=r'''
import json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1]);import live
task=json.loads(Path(sys.argv[2]).read_bytes());out=Path(sys.argv[3]);arm,mode,behavior=sys.argv[4:]
class Client(live.StubClient):
 def __init__(self,task):super().__init__(task);self.answers=0
 def __call__(self,messages,phase,n):
  if behavior=='bad':return '{',{}
  if phase=='answer' and behavior=='retrieve' and self.answers<3:
   self.answers+=1
   return json.dumps({'action':'fetch' if self.answers==1 else 'state_at','batch_id':1}),{}
  text,usage=super().__call__(messages,phase,n);reply=json.loads(text)
  if phase=='archive' and n==1 and behavior=='wrong':reply['state']['extra invented key']=999
  if phase=='quoted' and n==1 and behavior=='extra':
   last=reply['events'][-1];reply['events'] += [{**last,'op':'add'},{**last,'op':'sub'}]
  return json.dumps(reply),usage
if behavior=='gap':
 with patch.object(live.SnapshotStore,'save',side_effect=live.SnapshotStorageError('CPU fixture disk failure')):
  try:live.run_trial(task,arm,out,Client(task),retrieval_mode=mode)
  except live.InfrastructureError:pass
else:live.run_trial(task,arm,out,Client(task),retrieval_mode=mode)
'''
        subprocess.run([sys.executable,'-B','-c',script,str(audit.ENGINE),str(self.packet/item['task_path']),
            str(native.parent),item['arm'],item['retrieval_mode'],behavior],check=True,capture_output=True,text=True)
        native_result=audit.read(native)
        result=audit.audit_result(native.parent,self.tasks[item['case_id']],item,self.plan,'stub',None)
        outer_path=self.out/item['result_path'];outer=audit.read(outer_path)
        for key in ('status','score','phase_costs','action_counts','total_trial_wall_seconds',
                    'non_call_overhead_seconds','reference_checks_passed','quality_passed','cold_cost_interpretation',
                    'native_sha256','native_audit','snapshot_audit'):
            outer[key]=result[key]
        outer['native_artifacts']=native_result['artifacts']
        outer['native_auxiliary']={name:{'path':name,'sha256':audit.sha(native.parent/name)} for name in ('canonical.sqlite','identity.json')}
        outer['audit_error']=None
        self.write(outer_path,outer)
        return result

    def refresh_summary(self,abort=False):
        summary=audit.read(self.out/'summary.json');rows=[];observed=[]
        for item in self.plan['trials']:
            path=self.out/item['result_path']
            if path.exists():
                native=audit.read(path);row={**item,'status':native['status'],'quality_passed':native['quality_passed']};observed.append(row)
            else:row={**item,'status':'incomplete' if path.parent.exists() else 'unstarted',
                      'unstarted_reason':'campaign-infrastructure-abort' if abort else 'not-started'}
            rows.append(row)
        summary.update(trials=rows,unstarted_trials=[r for r in rows if r['status']=='unstarted'],
            observed_trials=len(observed),completed_trials=sum(r['status']=='completed' for r in observed),
            failed_trials=sum(r['status']=='failed' for r in observed),infrastructure_abort=abort,
            infrastructure_error='CPU fixture' if abort else None,
            status='failed' if abort else 'completed' if len(observed)==8 else 'running')
        self.write(self.out/'summary.json',summary)

    def test_portable_eight_stub_cells_are_not_model_evidence(self):
        report=audit.audit(self.out,self.packet)
        self.assertEqual(report['completed_trials'],8);self.assertEqual(len(report['trials']),8)
        self.assertTrue(all(r['reference_checks_passed'] for r in report['trials']))
        self.assertTrue(all(r['snapshot_audit']['complete_snapshot_evidence'] for r in report['trials']))
        self.assertFalse(any(r['quality_passed'] for r in report['trials']))
        self.assertFalse(report['continuation']['continuation_signal'])
        self.assertFalse(report['extension_admitted']);self.assertFalse(report['speed_gate_passed'])

    def test_snapshot_actions_and_repeated_cache_accounting(self):
        self.replace(1,'retrieve');self.refresh_summary();report=audit.audit(self.out,self.packet)
        counts=report['trials'][1]['action_counts']
        self.assertEqual(counts['requested_actions']['state_at'],2)
        self.assertEqual(counts['successful_distinct_retrievals']['state_at'],1)
        self.assertEqual(counts['repeated_retrieval_responses']['state_at'],1)

    def test_wrong_extra_archive_values_retained_not_oracle_corrected(self):
        self.replace(0,'wrong');self.refresh_summary();report=audit.audit(self.out,self.packet)
        row=report['trials'][0];self.assertTrue(row['integrity_passed']);self.assertFalse(row['reference_checks_passed'])
        self.assertEqual(row['native_audit']['correct'],24)
        self.assertEqual(row['native_audit']['checkpoints_exact'],11)

    def test_net_zero_extra_events_fail_quality_despite_exact_states_answers(self):
        self.replace(1,'extra');self.refresh_summary();row=audit.audit(self.out,self.packet)['trials'][1]
        self.assertEqual(row['native_audit']['correct'],24);self.assertEqual(row['native_audit']['checkpoints_exact'],12)
        self.assertFalse(row['reference_checks_passed']);self.assertEqual(row['native_audit']['accepted_events']['extra_events'],2)

    def test_bounded_failure_preserves_every_condition(self):
        self.replace(0,'bad');self.refresh_summary();report=audit.audit(self.out,self.packet)
        self.assertEqual(report['failed_trials'],1);self.assertEqual(report['completed_trials'],7)
        self.assertEqual(report['trials'][0]['phase_costs']['total']['calls'],3)

    def test_post_apply_snapshot_gap_preserves_infrastructure_and_tail(self):
        self.replace(1,'gap')
        for item in self.plan['trials'][2:]:shutil.rmtree((self.out/item['result_path']).parent)
        self.refresh_summary(True);report=audit.audit(self.out,self.packet)
        self.assertTrue(report['infrastructure_abort']);self.assertEqual(report['unstarted_trials'],6)
        self.assertEqual(report['failed_trials'],1);self.assertEqual(len(report['trials']),8)
        self.assertEqual(report['trials'][1]['snapshot_audit']['snapshot_write_gaps'],[{'batch_id':1,'quoted_apply_committed':True}])
        self.assertFalse(report['continuation']['continuation_signal'])

    def test_unstarted_incomplete_and_hidden_later_rows_are_checked(self):
        item=self.plan['trials'][-1];(self.out/item['result_path']).unlink();self.refresh_summary()
        report=audit.audit(self.out,self.packet);self.assertEqual(report['incomplete_trials'],1)
        shutil.rmtree((self.out/item['result_path']).parent);self.refresh_summary()
        self.assertEqual(audit.audit(self.out,self.packet)['unstarted_trials'],1)
        (self.out/self.plan['trials'][0]['result_path']).unlink();self.refresh_summary()
        with self.assertRaisesRegex(ValueError,'later trial'):audit.audit(self.out,self.packet)

    def test_rewritten_metrics_mode_question_identity_and_promotion_rejected(self):
        path=self.out/self.plan['trials'][0]['result_path'];original=audit.read(path)
        for key,value in (('retrieval_mode','history'),('question_sha256','0'*64),('quality_passed',True),('action_counts',{}),('speed_gate_passed',True)):
            changed=copy.deepcopy(original);changed[key]=value;self.write(path,changed)
            with self.assertRaises(ValueError):audit.audit(self.out,self.packet)

    def test_source_and_adjudication_bytes_cannot_be_rebound(self):
        packet=Path(self.temp.name)/'packet';shutil.copytree(self.packet,packet)
        path=packet/'source/adjudicated.json';path.write_bytes(path.read_bytes()+b'\n')
        plan=audit.read(packet/'plan.json');plan['files_sha256']['source/adjudicated.json']=audit.sha(path)
        self.write(packet/'plan.json',plan)
        with self.assertRaisesRegex(ValueError,'frozen reference input'):audit.load_packet(packet)


class ContinuationTests(unittest.TestCase):
    def rows(self):
        return [{'case_id':case,'condition':condition,'status':'completed','integrity_passed':True,
                 'quality_passed':True,'cold_cost_interpretation':True,
                 'answer_categories':{k:{'asked':8,'correct':8} for k in ('current','history','join')},
                 'total_trial_wall_seconds':85 if condition.endswith('H') else 100}
                for case,condition in audit.ORDER]

    def test_exact_cold_consistent_cost_signal_is_not_extension_admission(self):
        result=audit.continuation(self.rows(),'model');self.assertTrue(result['continuation_signal'])
        self.assertFalse(result['extension_admitted']);self.assertFalse(result['speed_gate_passed'])
        self.assertFalse(audit.continuation(self.rows(),'stub')['continuation_signal'])

    def test_accuracy_gain_requires_no_current_or_temporal_regression(self):
        rows=self.rows()
        for row in rows:row['total_trial_wall_seconds']=100
        rows[0]['answer_categories']['history']['correct']=7;rows[0]['quality_passed']=False
        self.assertTrue(audit.continuation(rows,'model')['continuation_signal'])
        rows[3]['answer_categories']['current']['correct']=7;rows[3]['quality_passed']=False
        self.assertFalse(audit.continuation(rows,'model')['continuation_signal'])

    def test_unknown_cache_one_case_saving_incomplete_and_failures_do_not_promote(self):
        for change in ('cache','slow','partial','infra','historywrong'):
            rows=self.rows()
            if change=='cache':
                for row in rows:row['cold_cost_interpretation']=False
            elif change=='slow':
                for row in rows:
                    if row['case_id']=='t02-theatre':row['total_trial_wall_seconds']=100
            elif change=='partial':rows[-1]['status']='unstarted'
            elif change=='historywrong':rows[1]['quality_passed']=False
            self.assertFalse(audit.continuation(rows,'model',change=='infra')['continuation_signal'],change)


if __name__=='__main__':unittest.main()
