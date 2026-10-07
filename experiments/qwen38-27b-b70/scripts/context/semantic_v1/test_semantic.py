"""CPU fixtures only; these are not annotations for the authored document packet."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from answers import INSTRUCTION, new_session, process
from diagnostics import answer_payload, compare_pairs, evaluate_trace, event_metrics, grade_answers
from tasks import compile_document, load_packet, public_task, reference_view, verify


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.source_sha = 'a'*64
        self.document = {'id': 'fixture-stress', 'pair_id': 'fixture', 'variant': 'stress', 'batches': [
            {'id': 1, 'text': 'alpha12 was set to 10. beta13 was set to 20. The seal was blue.'},
            {'id': 2, 'text': 'alpha12 was credited 5.'},
            {'id': 3, 'text': 'alpha12 was set to 7.'}], 'questions': [
            {'id': 'current', 'category': 'current', 'answer_type': 'int', 'text': 'What is the final alpha12 balance?'},
            {'id': 'past', 'category': 'history', 'answer_type': 'int', 'text': 'What was alpha12 at the end of batch 2?'},
            {'id': 'seal', 'category': 'history', 'answer_type': 'str', 'text': 'What was the batch 1 seal?'}]}
        def event(counter, op, amount, quote):
            return {'counter': counter, 'op': op, 'amount': amount, 'quote': quote}
        self.annotation = {'document_id': 'fixture-stress', 'source_sha256': self.source_sha,
            'batches': [
                {'batch_id': 1, 'events': [event('alpha12', 'set', 10, 'alpha12 was set to 10.'),
                    event('beta13', 'set', 20, 'beta13 was set to 20.')], 'state_after': {'alpha12':10, 'beta13':20}},
                {'batch_id': 2, 'events': [event('alpha12', 'add', 5, 'alpha12 was credited 5.')],
                    'state_after': {'alpha12':15, 'beta13':20}},
                {'batch_id': 3, 'events': [event('alpha12', 'set', 7, 'alpha12 was set to 7.')],
                    'state_after': {'alpha12':7, 'beta13':20}}],
            'answers': {'current':7, 'past':15, 'seal':'blue'}}
        self.task = compile_document(self.document, self.annotation, self.source_sha)

    def trace(self, arm='quoted'):
        rows=[]
        for i, batch in enumerate(self.annotation['batches'], 1):
            response = ({'events':copy.deepcopy(batch['events'])} if arm=='quoted'
                        else {'state':copy.deepcopy(batch['state_after'])} if arm=='archive'
                        else {'memory':'A recorded summary'})
            rows.append({'batch_id':i, 'attempts':[response]})
        return rows

    def test_compile_preserves_source_bytes_and_declared_history_integer(self):
        self.assertEqual(self.task['batches'], self.document['batches'])
        self.assertEqual(self.task['questions'], self.document['questions'])
        self.assertEqual(grade_answers(self.task, self.annotation['answers'])['correct'], 3)
        bad=dict(self.annotation['answers'], past='15')
        self.assertEqual(grade_answers(self.task, bad)['correct'], 2)
        verify(self.task)

    def test_prompt_allowlist_and_reference_copy_prevent_oracle_leak(self):
        public=public_task(self.task); payload=answer_payload(self.task)
        self.assertEqual(set(public), {'document_id','batches','questions','reading_conventions'})
        self.assertEqual(set(payload), {'instruction','questions','reading_conventions'})
        for forbidden in ('oracle', 'answers', 'after_batch', 'annotation_sha256', 'state_after'):
            self.assertNotIn(forbidden, public)
            self.assertNotIn(forbidden, payload)
        public['batches'][0]['text']='model mutation'
        public['questions'][0]['answer_type']='str'
        self.assertEqual(self.task['batches'][0]['text'], self.document['batches'][0]['text'])
        self.assertEqual(self.task['questions'][0]['answer_type'], 'int')
        with self.assertRaises(TypeError): reference_view(self.task)['after_batch'][0]['alpha12']=99
        self.assertIn('answer_type', INSTRUCTION)

    def test_missing_annotations_source_hash_and_identity_are_rejected(self):
        for annotation in (None, {}, dict(self.annotation, source_sha256='b'*64),
                           dict(self.annotation, document_id='another'), dict(self.annotation, batches=[])):
            with self.subTest(annotation=annotation):
                with self.assertRaises(ValueError): compile_document(self.document, annotation, self.source_sha)
        with self.assertRaisesRegex(ValueError, 'source hash'):
            compile_document(self.document, self.annotation, self.source_sha, expected_source_sha='b'*64)

    def test_wrong_order_nonliteral_event_and_inconsistent_state_are_rejected(self):
        mutations=[lambda a:a['batches'][0]['events'].reverse(),
            lambda a:a['batches'][1].update(batch_id=3),
            lambda a:a['batches'][2]['state_after'].update(alpha12=8),
            lambda a:a['batches'][1]['events'][0].update(op='double'),
            lambda a:a['batches'][1]['events'][0].update(amount=True),
            lambda a:a['batches'][1]['events'][0].update(quote='not delivered')]
        for mutation in mutations:
            broken=copy.deepcopy(self.annotation);mutation(broken)
            with self.assertRaises(ValueError):compile_document(self.document,broken,self.source_sha)

    def test_answer_coverage_types_and_prompt_fields_are_strict(self):
        for answers in ({'current':7},dict(self.annotation['answers'], unknown=1),
                        dict(self.annotation['answers'], past=True)):
            with self.assertRaises(ValueError):compile_document(self.document,dict(self.annotation,answers=answers),self.source_sha)
        doc=copy.deepcopy(self.document);doc['questions'][0]['expected_answer']=7
        with self.assertRaises(ValueError):compile_document(doc,self.annotation,self.source_sha)
        score=grade_answers(self.task,dict(self.annotation['answers'],unknown=1))
        self.assertFalse(score['valid']);self.assertFalse(score['exact_question_coverage'])

    def test_answer_protocol_uses_explicit_types_not_categories(self):
        session=new_session()
        process(session,{'action':'submit','answers':{'current':7,'past':15,'seal':'blue'}},self.task['questions'],None)
        self.assertTrue(session['completed'])
        session=new_session()
        process(session,{'action':'submit','answers':{'current':7,'past':'15','seal':'blue','unknown':3}},self.task['questions'],None)
        self.assertFalse(session['completed']);self.assertNotIn('past',session['answers'])
        self.assertIn('unknown question',session['feedback'])

    def test_omitted_posting_remains_visible_after_later_set_restores_final_state(self):
        trace=self.trace();trace[1]['attempts'][0]['events']=[]
        result=evaluate_trace(self.task,'quoted',trace,self.annotation['answers'])
        self.assertTrue(result['protocol_complete']);self.assertEqual(result['score']['correct'],3)
        self.assertTrue(result['final_state_exact']);self.assertFalse(result['all_checkpoint_states_exact'])
        self.assertEqual(result['batches'][1]['attempts'][0]['events']['omitted'],1)
        self.assertFalse(result['batches'][1]['state']['exact'])

    def test_semantic_substitution_and_spurious_events_are_separate(self):
        expected=self.annotation['batches'][1]['events']
        wrong=copy.deepcopy(expected);wrong[0].update(counter='beta13',op='sub',amount=4)
        metrics=event_metrics(wrong,expected)
        self.assertEqual(metrics['wrong_fields'],{'counter':1,'op':1,'amount':1})
        self.assertEqual(metrics['substitutions'],1);self.assertEqual(metrics['omitted'],0)
        self.assertEqual(metrics['semantic_f1'],0)
        spurious=copy.deepcopy(expected)+[{'counter':'beta13','op':'add','amount':3,'quote':'unrelated'}]
        self.assertEqual(event_metrics(spurious,expected)['spurious'],1)

    def test_valid_quote_span_variation_does_not_reduce_semantic_score(self):
        trace=self.trace();trace[0]['attempts'][0]['events'][0]['quote']=self.document['batches'][0]['text']
        result=evaluate_trace(self.task,'quoted',trace,self.annotation['answers'])
        self.assertTrue(result['protocol_complete'])
        self.assertEqual(result['batches'][0]['attempts'][0]['events']['matched'],2)
        self.assertEqual(result['batches'][0]['attempts'][0]['events']['semantic_f1'],1)
        self.assertTrue(result['all_checkpoint_states_exact'])

    def test_refused_quote_is_preserved_separately_from_semantic_match(self):
        trace=self.trace();bad=copy.deepcopy(trace[1]['attempts'][0]);bad['events'][0]['quote']='fabricated'
        trace[1]['attempts'].insert(0,bad)
        result=evaluate_trace(self.task,'quoted',trace,self.annotation['answers'])
        self.assertEqual(len(result['refusals']),1);self.assertTrue(result['protocol_complete'])
        attempts=result['batches'][1]['attempts']
        self.assertEqual(attempts[0]['events']['matched'],1)
        self.assertFalse(attempts[0]['accepted']);self.assertTrue(attempts[1]['accepted'])

    def test_all_three_arms_report_known_and_unobserved_state_honestly(self):
        for arm in ('summary','archive','quoted'):
            result=evaluate_trace(self.task,arm,self.trace(arm),self.annotation['answers'])
            self.assertTrue(result['protocol_complete']);self.assertEqual(result['score']['correct'],3)
            if arm=='summary':self.assertIsNone(result['all_checkpoint_states_exact'])
            else:self.assertTrue(result['all_checkpoint_states_exact'])

    def test_semantic_replay_refuses_ledger_operations_outside_its_contract(self):
        for op, amount in (('remove', None), ('reopen', 5)):
            with self.subTest(op=op):
                trace=self.trace()
                bad=copy.deepcopy(trace[1]['attempts'][0])
                bad['events'][0].update(op=op,amount=amount)
                trace[1]['attempts'].insert(0,bad)
                result=evaluate_trace(self.task,'quoted',trace,self.annotation['answers'])
                rejected=result['batches'][1]['attempts'][0]
                self.assertFalse(rejected['accepted'])
                self.assertIn('only set/add/sub',rejected['refused'])
                self.assertTrue(result['protocol_complete'])
                self.assertTrue(result['all_checkpoint_states_exact'])

    def test_answer_completion_is_distinct_from_ingestion_and_correctness(self):
        cases=[({},False,False,True,True),
               (dict(self.annotation['answers'],past='15'),False,True,True,False),
               (dict(self.annotation['answers'],past=True),False,True,True,False),
               (dict(self.annotation['answers'],unknown=1),False,False,False,True),
               (dict(self.annotation['answers'],past=999),True,True,True,True),
               (dict(self.annotation['answers'],past=None),True,True,True,True)]
        for answers,complete,coverage,valid,types_valid in cases:
            with self.subTest(answers=answers):
                result=evaluate_trace(self.task,'quoted',self.trace(),answers)
                self.assertTrue(result['ingestion_complete'])
                self.assertEqual(result['final_answer_complete'],complete)
                self.assertEqual(result['protocol_complete'],complete)
                self.assertEqual(result['score']['exact_question_coverage'],coverage)
                self.assertEqual(result['score']['valid'],valid)
                self.assertEqual(result['score']['answer_types_valid'],types_valid)
                if valid:self.assertLess(result['score']['correct'],result['score']['asked'])

    def test_ingestion_failure_prevents_completion_despite_complete_answers(self):
        trace=self.trace()
        trace[-1]['attempts'][0]['events'][0]['quote']='absent'
        result=evaluate_trace(self.task,'quoted',trace,self.annotation['answers'])
        self.assertFalse(result['ingestion_complete'])
        self.assertTrue(result['final_answer_complete'])
        self.assertFalse(result['protocol_complete'])
        self.assertEqual(result['score']['correct'],3)

    def test_malformed_event_container_retains_complete_metric_schema(self):
        expected=self.annotation['batches'][1]['events']
        malformed=event_metrics(None,expected)
        self.assertEqual(set(malformed),set(event_metrics([],expected)))
        self.assertFalse(malformed['valid_format'])
        self.assertEqual(malformed['missed_events'],1)
        self.assertIsNone(malformed['semantic_f1'])

    def test_trace_hash_binds_original_responses_answers_and_refusals(self):
        trace=self.trace('summary')
        def evaluate(rows=trace, answers=None, refusals=()):
            return evaluate_trace(self.task,'summary',rows,
                                  self.annotation['answers'] if answers is None else answers,
                                  refusals=refusals)
        original=evaluate()
        reordered=[dict(reversed(list(row.items()))) for row in trace]
        self.assertEqual(original['trace_sha256'],evaluate(reordered)['trace_sha256'])
        changed=copy.deepcopy(trace)
        changed[1]['attempts'][0]['memory']='A different recorded summary'
        modified=evaluate(changed)
        self.assertNotEqual(original['trace_sha256'],modified['trace_sha256'])
        self.assertEqual(original['task_sha256'],modified['task_sha256'])
        self.assertNotEqual(original['trace_sha256'],evaluate(answers={})['trace_sha256'])
        self.assertNotEqual(original['trace_sha256'],evaluate(refusals=['recorded refusal'])['trace_sha256'])

    def test_pair_comparison_requires_both_versions_and_keeps_failures(self):
        result=evaluate_trace(self.task,'archive',self.trace('archive'),self.annotation['answers'])
        with self.assertRaises(ValueError):compare_pairs([result])
        control=copy.deepcopy(result);control['variant']='control';control['protocol_complete']=False
        self.assertFalse(compare_pairs([result,control])[0]['control']['protocol_complete'])
        with self.assertRaises(ValueError):compare_pairs([result,result,control])

    def test_file_loader_binds_actual_packet_bytes_and_exact_annotation_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            docs=Path(temp)/'documents.json';annotation=Path(temp)/'annotations.json'
            docs.write_text(json.dumps({'documents':[self.document]}));sha=hashlib.sha256(docs.read_bytes()).hexdigest()
            native=copy.deepcopy(self.annotation);native['source_sha256']=sha
            sources=[]
            for name in ('independent.json','review.json'):
                path=Path(temp)/name;path.write_text(json.dumps({'reviewer':name}))
                sources.append({'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            wrapper={'schema':'context-semantic-adjudicated.v1','source_sha256':sha,'documents':[native],
                     'annotation_sources':sources}
            annotation.write_text(json.dumps(wrapper))
            self.assertEqual(len(load_packet(docs,annotation)),1)
            for invalid in (dict(sources[0],path='../outside.json'),dict(sources[0],path='/absolute.json'),
                            dict(sources[0],sha256='0'*64),sources[1]):
                wrapper['annotation_sources']=[invalid,sources[1]];annotation.write_text(json.dumps(wrapper))
                with self.assertRaises(ValueError):load_packet(docs,annotation)
            wrapper['annotation_sources']=sources;annotation.write_text(json.dumps(wrapper))
            docs.write_text(docs.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'source hash'):load_packet(docs,annotation)
            docs.write_text(docs.read_text()[:-1]);wrapper['documents']=[];annotation.write_text(json.dumps(wrapper))
            with self.assertRaisesRegex(ValueError,'annotation per document'):load_packet(docs,annotation)

    def test_independently_adjudicated_development_packet_compiles_without_changes(self):
        root=Path(__file__).resolve().parents[3]/'data/2026-10-07-context-semantic-development'
        tasks=load_packet(root/'documents.json',root/'adjudicated.json')
        packet=json.loads((root/'documents.json').read_bytes());raw=packet['documents']
        self.assertEqual(len(tasks),12);self.assertEqual(sum(len(t['questions']) for t in tasks),84)
        for task,document in zip(tasks,raw):
            verify(task)
            self.assertEqual(task['batches'],document['batches'])
            self.assertEqual(len(task['annotation_sources']),2)
            self.assertEqual(public_task(task)['reading_conventions'],packet['reading_conventions'])
            trace=[{'batch_id':n,'attempts':[{'events':events}]} for n,events in enumerate(task['oracle']['events'],1)]
            result=evaluate_trace(task,'quoted',trace,task['oracle']['answers'])
            self.assertTrue(result['protocol_complete']);self.assertTrue(result['all_checkpoint_states_exact'])
            self.assertEqual(result['score']['correct'],7)


if __name__=='__main__':unittest.main()
