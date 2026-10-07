"""CPU-only native audit corruption checks; no live calls or runtime changes."""
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

import audit_semantic_v1 as native

RUNTIME = Path(__file__).parent/'semantic_v1'
sys.path.insert(0,str(RUNTIME))
import live
from test_live import FakeModel
from tasks import load_packet


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.packet=Path(__file__).resolve().parents[2]/'data/2026-10-07-context-semantic-development'
        cls.base=Path(cls.temp.name)/'base'
        live.execute(cls.packet/'documents.json',cls.packet/'adjudicated.json',cls.base/'diagnostic',stub=True)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'output'
        shutil.copytree(self.base,self.root)
        self.plan=native.read(self.root/'diagnostic/plan.json')
        self.item=next(r for r in self.plan['trials'] if r['arm']=='quoted')
        self.path=self.root/'diagnostic'/self.item['result_path']

    def write(self,path,value):
        path.write_text(json.dumps(value))

    def result_edit(self,mutate):
        data=native.read(self.path);mutate(data);self.write(self.path,data)

    def test_gold_wiring_independent_counts_and_unknown_tokens(self):
        result=native.audit(self.root,self.packet)
        self.assertEqual(result['measurement_kind'],'stub')
        self.assertEqual(result['completed_trials'],36)
        self.assertTrue(result['arms']['quoted']['all_accepted_events_exact'])
        self.assertEqual(result['arms']['quoted']['accepted_events']['matched'],84)
        self.assertEqual(result['arms']['quoted']['accepted_events']['extra_events'],0)
        for arm,row in result['arms'].items():
            self.assertEqual((row['correct'],row['asked']),(84,84))
            self.assertEqual(row['checkpoints_exact'],0 if arm=='summary' else 48)
            for key in ('prompt_tokens','completion_tokens','reasoning_tokens','cached_tokens'):
                self.assertIsNone(row[key])

    def test_artifact_corruption_and_missing_binding_rejected(self):
        (self.path.parent/'calls.jsonl').write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'artifact hash'):native.audit(self.root,self.packet)
        shutil.copyfile(self.base/'diagnostic'/self.item['result_path'].replace('result.json','calls.jsonl'),self.path.parent/'calls.jsonl')
        self.result_edit(lambda r:r['artifacts'].pop('trace.json'))
        with self.assertRaisesRegex(ValueError,'bindings missing'):native.audit(self.root,self.packet)

    def test_source_kind_and_task_bindings_rejected(self):
        original=native.read(self.path)
        for key,value in (('task_sha256','0'*64),('source_sha256','0'*64),('measurement_kind','model')):
            changed=copy.deepcopy(original);changed[key]=value;self.write(self.path,changed)
            with self.subTest(key=key),self.assertRaises(ValueError):native.audit(self.root,self.packet)

    def test_matrix_duplicate_and_summary_mismatch_rejected(self):
        altered=copy.deepcopy(self.plan);altered['trials'][1]=altered['trials'][0]
        self.write(self.root/'diagnostic/plan.json',altered)
        with self.assertRaisesRegex(ValueError,'matrix'):native.audit(self.root,self.packet)
        self.write(self.root/'diagnostic/plan.json',self.plan)
        path=self.root/'diagnostic/summary.json';summary=native.read(path);summary['completed_trials']=35;self.write(path,summary)
        with self.assertRaisesRegex(ValueError,'summary total'):native.audit(self.root,self.packet)

    def test_checkpoint_flags_and_sqlite_final_state_are_recomputed(self):
        result=native.read(self.path);result['batches'][0]['state']['exact']=False
        trace=native.read(self.path.parent/'trace.json');trace['batches']=result['batches']
        self.write(self.path.parent/'trace.json',trace)
        result['artifacts']['trace.json']['sha256']=native.sha(self.path.parent/'trace.json');self.write(self.path,result)
        with self.assertRaisesRegex(ValueError,'checkpoint metrics'):native.audit(self.root,self.packet)
        shutil.copytree(self.base/'diagnostic'/self.path.parent.name,self.path.parent,dirs_exist_ok=True)
        with sqlite3.connect(self.path.parent/'canonical.sqlite') as conn:
            conn.execute("UPDATE current_state SET value='999' WHERE counter='amber10'")
        with self.assertRaisesRegex(ValueError,'final SQLite'):native.audit(self.root,self.packet)

    def test_unstarted_trial_remains_visible_without_invented_completion(self):
        self.path.unlink()
        path=self.root/'diagnostic/summary.json';summary=native.read(path)
        summary['trials']=[r for r in summary['trials'] if r['result_path']!=self.item['result_path']]
        summary.update(status='running',observed_trials=35,completed_trials=35);self.write(path,summary)
        result=native.audit(self.root,self.packet)
        self.assertEqual(result['unstarted_trials'],1)
        self.assertEqual(result['arms']['quoted']['asked'],77)
        self.assertEqual(result['arms']['quoted']['planned_questions'],84)
        self.assertFalse(result['arms']['quoted']['cold_cache_known'])

    def test_usage_null_partial_and_invalid_are_unknown(self):
        for calls in ([{'usage':None}],[{'usage':{'prompt_tokens_details':None}}],[{'usage':{'prompt_tokens':True,'completion_tokens':-1}}]):
            totals=native.usage_totals(calls)
            self.assertFalse(totals['cold_cache_known'])
            self.assertIsNone(totals['reasoning_tokens'])
            self.assertIsNone(totals['cached_tokens'])
        totals=native.usage_totals([{'usage':{'prompt_tokens':10,'completion_tokens':3,'prompt_tokens_details':{'cached_tokens':0}}}])
        self.assertEqual(totals['prompt_tokens'],10);self.assertIsNone(totals['reasoning_tokens'])
        self.assertTrue(totals['cold_cache_known'])

    def test_saved_answer_rewrite_cannot_replace_raw_model_evidence(self):
        result=native.read(self.path)
        task=next(t for t in load_packet(self.packet/'documents.json',self.packet/'adjudicated.json')
                  if t['document_id']==self.item['document_id'])
        key=next(k for k,v in result['answers'].items() if type(v) is int)
        result['answers'][key]=999
        result['answer_protocol']['answers'][key]=999
        result['score']=native.answer_score(task,result['answers'])
        session_path=self.path.parent/'answer-session.json'
        self.write(session_path,result['answer_protocol'])
        result['artifacts']['answer-session.json']['sha256']=native.sha(session_path)
        self.write(self.path,result)
        with self.assertRaisesRegex(ValueError,'saved answers differ'):native.audit(self.root,self.packet)

    def test_archive_state_is_derived_from_accepted_response(self):
        item=next(r for r in self.plan['trials'] if r['arm']=='archive')
        path=self.root/'diagnostic'/item['result_path'];result=native.read(path)
        result['batches'][0]['observed_state']['amber10']=999
        result['batches'][0]['state']=native.state_metrics(result['batches'][0]['observed_state'],{'amber10':10,'birch11':20})
        trace_path=path.parent/'trace.json';trace=native.read(trace_path);trace['batches']=result['batches'];self.write(trace_path,trace)
        result['artifacts']['trace.json']['sha256']=native.sha(trace_path);self.write(path,result)
        with self.assertRaisesRegex(ValueError,'checkpoint metrics'):native.audit(self.root,self.packet)

    def test_failed_model_trial_is_retained_and_source_completeness_is_separate(self):
        task=next(t for t in load_packet(self.packet/'documents.json',self.packet/'adjudicated.json') if t['document_id']==self.item['document_id'])
        directory=Path(self.temp.name)/'failed'
        class ConsistentFake(FakeModel):
            def __call__(self,*args):
                text,usage=super().__call__(*args)
                self.last_response_metadata['response_message']['content']=text
                return text,usage
        result=live.run_trial(task,'quoted',directory,ConsistentFake(task,'malformed'))
        plan=copy.deepcopy(self.plan);plan['measurement_kind']='model'
        row=native.audit_trial(directory,result,task,self.item,plan)
        self.assertEqual(row['status'],'failed');self.assertEqual(row['correct'],0)
        self.assertTrue(row['delivered_text_exact']);self.assertFalse(row['source_delivery_complete'])
        self.assertEqual(row['checkpoints_checked'],1)

    def test_extra_postings_cannot_hide_behind_exact_net_balance(self):
        task=next(t for t in load_packet(self.packet/'documents.json',self.packet/'adjudicated.json')
                  if t['document_id']==self.item['document_id'])
        class NetZeroFake(FakeModel):
            def __call__(self,messages,phase,batch_id):
                text,usage=super().__call__(messages,phase,batch_id)
                reply=json.loads(text)
                if phase=='quoted' and batch_id==2:
                    event=reply['events'][0]
                    reply['events'] += [{**event,'op':'add'},
                        {**event,'op':'sub','quote':task['batches'][1]['text']}]
                text=json.dumps(reply)
                self.last_response_metadata['response_message']['content']=text
                return text,usage
        directory=Path(self.temp.name)/'net-zero'
        result=live.run_trial(task,'quoted',directory,NetZeroFake(task))
        self.assertEqual(result['status'],'completed')
        self.assertTrue(result['all_checkpoint_states_exact'])
        plan=copy.deepcopy(self.plan);plan['measurement_kind']='model'
        row=native.audit_trial(directory,result,task,self.item,plan)
        self.assertEqual(row['checkpoints_exact'],4)
        self.assertFalse(row['all_accepted_events_exact'])
        self.assertEqual(row['accepted_events']['extra_events'],2)
        second=next(r for r in row['event_attempts'] if r['batch_id']==2)
        self.assertEqual((second['expected'],second['predicted'],second['matched']),(1,3,1))
        self.assertFalse(second['exact_order'])
        # Corrupt the native semantic metrics while preserving the balance and
        # the trace binding: independent tuple matching must still reject it.
        result['batches'][1]['attempts'][0]['events']['matched']=3
        trace_path=directory/'trace.json';trace=native.read(trace_path)
        trace['batches']=result['batches'];self.write(trace_path,trace)
        result['artifacts']['trace.json']['sha256']=native.sha(trace_path)
        with self.assertRaisesRegex(ValueError,'independent tuple'):
            native.audit_trial(directory,result,task,self.item,plan)

    def test_semantic_matching_keeps_malformed_and_quote_variation_separate(self):
        gold=[{'counter':'amber10','op':'add','amount':3,'quote':'short span'}]
        varied=[dict(gold[0],quote='a different span'),None]
        metrics=native.semantic_events(varied,gold)
        self.assertEqual(metrics['matched'],1)
        self.assertEqual(metrics['malformed'],1)
        self.assertEqual(metrics['extra_events'],1)
        self.assertFalse(metrics['exact_order'])
        self.assertTrue(native.semantic_events(varied[:1],gold)['exact_order'])


if __name__=='__main__':unittest.main()
