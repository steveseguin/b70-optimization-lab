"""Generated-study CPU checks; no endpoint or GPU invocation."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock,patch

import engine
import generator
import runner


@unittest.skipUnless(runner.DEFAULT_TOKENIZER.is_file() and runner.DEFAULT_PYTHON.is_file(),
                     'local tokenizer and its interpreter are required for measured integration checks')
class SparseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sparse-tests-')
        cls.root=Path(cls.temp.name);cls.packet=cls.root/'packet'
        cls.bundle=runner.prepare(cls.packet)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_fixed_generated_documents_questions_and_untouched_counter(self):
        for count in (8,128):
            case=generator.make_case(count);task=case['task'];initial=case['metadata']['initialization_batches']
            self.assertEqual(case,generator.make_case(count))
            self.assertEqual(len(task['batches']),initial+16);self.assertEqual(len(task['questions']),24)
            self.assertEqual(len(task['oracle']['after_batch'][-1]),count)
            self.assertTrue(all(len(events)<=16 for events in task['oracle']['events'][:initial]))
            self.assertTrue(all(len(events)==3 for events in task['oracle']['events'][initial:]))
            reserve=case['metadata']['untouched_counter']
            self.assertTrue(all(e['counter']!=reserve for events in task['oracle']['events'][initial:] for e in events))
            self.assertTrue(any(reserve in q['text'] for q in task['questions'] if q['category']=='current'))
            self.assertEqual({category:sum(q['category']==category for q in task['questions']) for category in ('current','history','join')},
                             {'current':8,'history':8,'join':8})
            self.assertTrue(all(q['answer_type']=='int' for q in task['questions']))
            self.assertEqual(task['generated_provenance']['kind'],'programmatically-generated')
            self.assertNotIn('annotation_sources',task)

    def test_independent_reference_reader_uses_emitted_review_source(self):
        original=generator.replay_source
        def corrupted(document):
            document['batches'][-1]['text']=document['batches'][-1]['text'].replace(
                'review-n8-0 concerns ticket-n8-0.','review-n8-0 concerns missing-ticket.')
            return original(document)
        with patch.object(generator,'replay_source',side_effect=corrupted):
            with self.assertRaises((KeyError,ValueError)):generator.make_case(8)

    def test_real_local_tokenizer_and_prompt_checks_fit(self):
        receipt=self.bundle['budget']
        self.assertTrue(receipt['all_reference_prompts_fit']);self.assertTrue(receipt['all_reference_emissions_fit'])
        self.assertEqual(len(receipt['trials']),4)
        self.assertEqual(receipt['tokenizer_sha256'],engine.sha(receipt['tokenizer_path']))
        for row in receipt['trials']:
            for phase,metrics in row['phases'].items():
                self.assertLessEqual(metrics['max_reference_response_tokens'],8192 if phase=='answer' else 4096)
                self.assertLessEqual(metrics['max_prompt_bytes_with_ascii_memory_allowance'],32768)

    def test_plan_policy_and_receipt_tampering_are_rejected(self):
        plan_path=self.packet/'plan.json';original=plan_path.read_bytes();plan=json.loads(original)
        for mutate in (lambda p:p.update(max_answer_calls=99),lambda p:p['generation'].update(seed=84),
                       lambda p:p['trials'].reverse(),lambda p:p.update(holdout_admitted=True)):
            changed=copy.deepcopy(plan);mutate(changed);plan_path.write_text(json.dumps(changed))
            try:
                with self.assertRaises(ValueError):runner.validate_packet(self.packet)
            finally:plan_path.write_bytes(original)
        receipt=self.packet/'budget-receipt.json';saved=receipt.read_bytes();bad=json.loads(saved)
        bad['trials'][0]['phases']['steady']['max_reference_response_tokens']=1;receipt.write_text(json.dumps(bad))
        altered=copy.deepcopy(plan);altered['files_sha256']['budget-receipt.json']=engine.sha(receipt);plan_path.write_text(json.dumps(altered))
        try:
            with self.assertRaisesRegex(ValueError,'recomputation'):runner.validate_packet(self.packet)
        finally:receipt.write_bytes(saved);plan_path.write_bytes(original)

    def native(self,arm='quoted'):
        task=self.bundle['tasks']['sparse-n8-seed83'];rows=[]
        for index,(events,state) in enumerate(zip(task['oracle']['events'],task['oracle']['after_batch']),1):
            reply={'events':copy.deepcopy(events)} if arm=='quoted' else {'state':copy.deepcopy(state)}
            rows.append({'batch_id':index,'accepted':True,'attempts':[{'accepted':True,'response':reply}],
                         'observed_state':copy.deepcopy(state)})
        return task,{'status':'completed','protocol_complete':True,'ingestion_complete':True,
            'final_answer_complete':True,'resumed':False,'batches':rows,'answers':copy.deepcopy(task['oracle']['answers'])}

    def test_semantic_net_zero_wrong_order_and_checkpoint_errors_cannot_hide(self):
        task,native=self.native();self.assertTrue(runner.independent_quality(task,'quoted',native))
        altered=copy.deepcopy(native);events=altered['batches'][1]['attempts'][0]['response']['events']
        event=copy.deepcopy(events[0]);event.update(op='add',amount=1);events.append(event)
        event=copy.deepcopy(event);event['op']='sub';events.append(event)
        self.assertFalse(runner.independent_quality(task,'quoted',altered))
        altered=copy.deepcopy(native);altered['batches'][0]['attempts'][0]['response']['events'].reverse()
        self.assertFalse(runner.independent_quality(task,'quoted',altered))
        altered=copy.deepcopy(native);altered['batches'][1]['observed_state']={}
        self.assertFalse(runner.independent_quality(task,'quoted',altered))
        native['batches'][0]['attempts'].insert(0,{'accepted':False,'error':'retained refusal'})
        self.assertTrue(runner.independent_quality(task,'quoted',native))

    def test_cost_totals_include_init_steady_answers_and_unknown_usage(self):
        rows=[{'phase':'quoted','batch_id':1,'seconds':2,'prompt_bytes':40,'usage':{'prompt_tokens':10,'completion_tokens':3,'prompt_tokens_details':{'cached_tokens':0}}},
              {'phase':'quoted','batch_id':2,'seconds':4,'prompt_bytes':60,'usage':{}},
              {'phase':'answer','batch_id':None,'seconds':3,'prompt_bytes':50,'usage':{'prompt_tokens':20,'completion_tokens':8,'prompt_tokens_details':{'cached_tokens':0}}}]
        result=runner.phase_costs(rows,1)
        self.assertEqual(result['total']['calls'],3);self.assertEqual(result['total']['client_call_seconds'],9)
        self.assertEqual(result['initialization']['completion_tokens'],3)
        self.assertIsNone(result['total']['completion_tokens']);self.assertFalse(result['total']['cache_complete'])

    def test_owned_cpu_child_is_terminated_and_reaped_on_cancellation(self):
        child=Mock();child.communicate.side_effect=runner.StopRequested('cancel');child.poll.return_value=None
        child.wait.return_value=0
        with patch.object(runner.subprocess,'Popen',return_value=child):
            with self.assertRaises(runner.StopRequested):runner.run_owned(['cpu-worker'])
        child.terminate.assert_called_once();child.wait.assert_called_once_with(timeout=5);child.kill.assert_not_called()
        child=Mock();child.communicate.side_effect=runner.StopRequested('cancel');child.poll.return_value=None
        child.wait.side_effect=[subprocess.TimeoutExpired('cpu-worker',5),0]
        with patch.object(runner.subprocess,'Popen',return_value=child):
            with self.assertRaises(runner.StopRequested):runner.run_owned(['cpu-worker'])
        child.kill.assert_called_once();self.assertEqual(child.wait.call_count,2)

    def test_complete_four_trial_stub_preserves_generated_scope_and_costs(self):
        out=self.root/'stub-results';result=runner.execute(self.packet,out,stub=True)
        self.assertEqual(result['observed_trials'],4);self.assertEqual(result['completed_trials'],4)
        self.assertEqual([(r['counter_count'],r['arm']) for r in result['trials']],list(runner.ORDER))
        self.assertEqual(result['measurement_kind'],'stub');self.assertFalse(result['speed_gate_passed'])
        for row in result['trials']:
            trial=json.loads((out/row['result_path']).read_bytes())
            self.assertTrue(trial['reference_checks_passed']);self.assertFalse(trial['quality_passed'])
            self.assertFalse(trial['cold_cost_interpretation']);self.assertEqual(trial['phase_costs']['steady']['calls'],16)
            self.assertEqual(trial['native_sha256'],engine.sha(out/row['native_result_path']))

    def fake_terminal_worker(self, *, infrastructure=False):
        """Unit-only native fixtures; never label fabricated evidence as model."""
        invoked=[]
        def worker(argv,**kwargs):
            invoked.append(argv)
            directory=Path(argv[argv.index('--out')+1]);directory.mkdir()
            task=json.loads(Path(argv[argv.index('--task')+1]).read_bytes())
            arm=argv[argv.index('--arm')+1];failed=len(invoked)==1
            batches=[]
            if not failed:
                for index,(events,state) in enumerate(zip(task['oracle']['events'],task['oracle']['after_batch']),1):
                    response={'events':events} if arm=='quoted' else {'state':state}
                    batches.append({'batch_id':index,'accepted':True,'observed_state':state,
                                    'attempts':[{'accepted':True,'response':response}]})
            calls=directory/'calls.jsonl';calls.write_text('')
            native={'schema':'semantic-live-trial.v1','protocol':'semantic-development-live-v1',
                'measurement_kind':'stub','unit_fixture':True,'resumed':False,'status':'failed' if failed else 'completed',
                'failure_kind':('infrastructure' if infrastructure else 'model') if failed else None,
                'task_sha256':task['task_sha256'],'arm':arm,'source_code_sha256':self.bundle['plan']['engine_source_sha256'],
                'server_identity':None,'wall_seconds':0,'batches':batches,
                'answers':{} if failed else task['oracle']['answers'],
                'protocol_complete':not failed,'ingestion_complete':not failed,'final_answer_complete':not failed,
                'artifacts':{'calls':{'path':'calls.jsonl','sha256':engine.sha(calls)}}}
            for key in ('context_limit_utf8_bytes','memory_limit_utf8_bytes','max_ingestion_attempts',
                        'max_retrieval','max_answer_calls','ingestion_generation','answer_generation'):
                native[key]=self.bundle['plan'][key]
            (directory/'result.json').write_text(json.dumps(native))
            return subprocess.CompletedProcess(argv,1 if infrastructure and failed else 0)
        return invoked,worker

    def test_bounded_native_failure_retains_four_ordered_trials(self):
        invoked,worker=self.fake_terminal_worker();out=self.root/'bounded-fixture'
        with patch.object(runner,'validate_packet',return_value=self.bundle),patch.object(runner,'run_owned',side_effect=worker):
            result=runner.execute(self.packet,out,stub=True)
        self.assertEqual(len(invoked),4);self.assertEqual(result['observed_trials'],4)
        self.assertEqual(result['failed_trials'],1);self.assertEqual(result['completed_trials'],3)
        self.assertFalse(result['infrastructure_abort']);self.assertEqual(result['status'],'completed')
        self.assertEqual([(r['counter_count'],r['arm']) for r in result['trials']],list(runner.ORDER))
        for index,row in enumerate(result['trials']):
            outer=json.loads((out/row['result_path']).read_bytes())
            self.assertEqual(outer['reference_checks_passed'],index>0)
            self.assertEqual(outer['measurement_kind'],'stub');self.assertFalse(outer['quality_passed'])
        first=json.loads((out/result['trials'][0]['native_result_path']).read_bytes())
        self.assertEqual(first['failure_kind'],'model');self.assertEqual(first['answers'],{})

    def test_worker_infrastructure_failure_retains_partial_evidence_and_aborts(self):
        invoked,worker=self.fake_terminal_worker(infrastructure=True);out=self.root/'infrastructure-fixture'
        with patch.object(runner,'validate_packet',return_value=self.bundle),patch.object(runner,'run_owned',side_effect=worker):
            with self.assertRaisesRegex(RuntimeError,'infrastructure failure'):
                runner.execute(self.packet,out,stub=True)
        result=json.loads((out/'summary.json').read_bytes())
        self.assertEqual(len(invoked),1);self.assertEqual(result['observed_trials'],1)
        self.assertTrue(result['infrastructure_abort']);self.assertEqual(result['status'],'failed')
        self.assertEqual(result['failed_trials'],1);self.assertEqual(result['completed_trials'],0)
        row=result['trials'][0];self.assertTrue((out/row['result_path']).is_file())
        native=json.loads((out/row['native_result_path']).read_bytes())
        self.assertEqual(native['failure_kind'],'infrastructure')
        self.assertFalse((out/Path(self.bundle['plan']['trials'][1]['result_path']).parent).exists())


class PortableSparseTests(unittest.TestCase):
    """Source, semantics and child ownership checks require only Python stdlib."""
    @classmethod
    def setUpClass(cls):
        cls.bundle={'tasks':{f'sparse-n{count}-seed83':generator.make_case(count)['task']
                             for count in (8,128)}}

    native=SparseTests.native
    test_fixed_generated_documents_questions_and_untouched_counter=SparseTests.test_fixed_generated_documents_questions_and_untouched_counter
    test_independent_reference_reader_uses_emitted_review_source=SparseTests.test_independent_reference_reader_uses_emitted_review_source
    test_semantic_net_zero_wrong_order_and_checkpoint_errors_cannot_hide=SparseTests.test_semantic_net_zero_wrong_order_and_checkpoint_errors_cannot_hide
    test_cost_totals_include_init_steady_answers_and_unknown_usage=SparseTests.test_cost_totals_include_init_steady_answers_and_unknown_usage
    test_owned_cpu_child_is_terminated_and_reaped_on_cancellation=SparseTests.test_owned_cpu_child_is_terminated_and_reaped_on_cancellation


if __name__=='__main__':unittest.main()
