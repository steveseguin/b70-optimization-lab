import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from answers import new_session, process, search_pattern
from ledger import CanonicalLedger
from pilot import run, StubClient
from tasks import make_task


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CanonicalLedger(Path(self.tmp.name)/'source.sqlite')
        self.store.deliver(1, 'The delivery seal for batch 2 was copper. ticket-7-0 belongs here.')
        self.store.deliver(2, 'The delivery seal for batch 20 was silver.')
        self.session = new_session()
        self.questions = [{'id':'a','category':'current'}, {'id':'b','category':'history'}]

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def step(self, reply, cap=24):
        return process(self.session, reply, self.questions, self.store, cap)

    def test_observed_mixed_partial_answers_search_does_not_finish(self):
        result = self.step({'answers': {'a':12}, 'search':'batch 2'})
        self.assertEqual(self.session['answers'], {'a':12})
        self.assertFalse(self.session['completed'])
        self.assertEqual(result['total_matches'], 1)
        self.assertEqual(result['matches'][0]['batch_id'], 1)

    def test_complete_answers_alone_need_explicit_submission(self):
        self.step({'answers': {'a':12,'b':'copper'}})
        self.assertFalse(self.session['completed'])
        self.step({'action':'submit'})
        self.assertTrue(self.session['completed'])

    def test_incomplete_submission_then_update_and_unknown(self):
        self.step({'action':'submit','answers':{'a':12}})
        self.assertFalse(self.session['completed'])
        self.assertIn('incomplete',self.session['feedback'])
        self.step({'action':'update','answers':{'a':13,'b':None}})
        self.step({'action':'submit'})
        self.assertEqual(self.session['answers'], {'a':13,'b':None})
        self.assertTrue(self.session['completed'])

    def test_invalid_values_and_ambiguous_action_preserve_valid_answers(self):
        self.step({'action':'submit','answers':{'a':True,'b':'ok','unknown':12}})
        self.assertEqual(self.session['answers'], {'b':'ok'})
        self.assertFalse(self.session['completed'])
        self.step({'action':'search','query':'batch 2','batch_id':2,'answers':{'a':12}})
        self.assertEqual(self.session['answers'], {'a':12,'b':'ok'})
        self.assertEqual(self.session['retrievals'],0)
        self.assertIn('ambiguous', self.session['feedback'])

    def test_duplicate_promotes_cached_evidence_without_spending_retrieval(self):
        first=self.step({'action':'fetch','batch_id':1})
        self.step({'action':'fetch','batch_id':2})
        with patch.object(self.store,'get',side_effect=AssertionError('must use cache')):
            again=self.step({'action':'fetch','batch_id':1})
        self.assertEqual(again, first)
        self.assertEqual(self.session['retrievals'],2)
        self.assertEqual(self.session['recent'],['fetch:2','fetch:1'])
        self.assertIn('cached',self.session['feedback'])

    def test_missing_fetch_not_success_zero_hit_search_counts(self):
        self.step({'action':'fetch','batch_id':999})
        self.assertEqual(self.session['retrievals'],0)
        self.assertIn('error',self.session['feedback'])
        self.step({'action':'search','query':'no matches'})
        self.assertEqual(self.session['retrievals'],1)

    def test_retrieval_cap_still_allows_cached_fetch_and_submission(self):
        self.step({'action':'fetch','batch_id':1},1)
        self.step({'action':'fetch','batch_id':2},1)
        self.assertIn('exhausted',self.session['feedback'])
        self.assertIsNotNone(self.step({'action':'fetch','batch_id':1},1))
        self.step({'action':'submit','answers':{'a':None,'b':None}},1)
        self.assertTrue(self.session['completed'])

    def test_numeric_identifier_boundaries(self):
        for query,good,bad in [('batch 2','batch 2 was','batch 20 was'),('ticket-7-0','ticket-7-0 belongs','ticket-7-01 belongs'),('2','batch 2 was','batch 12 was')]:
            self.assertIsNotNone(search_pattern(query).search(good))
            self.assertIsNone(search_pattern(query).search(bad))


class RecoveryTests(unittest.TestCase):
    def test_logged_mixed_reply_replayed_after_crash_before_state_save(self):
        import pilot
        task=make_task(7,4,0)
        original=pilot.atomic
        class Client(StubClient):
            def __call__(self,messages,phase,batch_id):
                if phase=='answer':
                    payload=json.loads(messages[-1]['content'])
                    if not payload['saved_answers']:
                        return json.dumps({'answers':{'current-0':12},'search':'ticket-7-0'}),{}
                    assert payload['saved_answers']['current-0']==12
                    assert payload['remaining_answer_calls_including_this']==31
                    assert payload['retrieved']
                return super().__call__(messages,phase,batch_id)
        def crash(path,value):
            if path.name=='answer-session.json' and value['answers']:
                raise RuntimeError('loss after response log, before state commit')
            original(path,value)
        with tempfile.TemporaryDirectory() as d:
            with patch('pilot.atomic',side_effect=crash):
                with self.assertRaises(RuntimeError):run(task,'quoted',d,Client(task))
            result=run(task,'quoted',d,Client(task))
            self.assertEqual(result['score']['correct'],24)
            self.assertEqual(result['answer_protocol'],{'calls':2,'retrievals':1})
            self.assertTrue(result['resumed'])

    def test_repeated_search_hits_action_cap_preserves_partials_on_resume(self):
        task=make_task(7,4,0)
        class Repeater(StubClient):
            def __call__(self,messages,phase,batch_id):
                if phase=='answer':return '{"answers":{"current-0":12},"search":"batch 2"}',{}
                return super().__call__(messages,phase,batch_id)
        with tempfile.TemporaryDirectory() as d:
            for attempt in range(2):
                with self.assertRaisesRegex(ValueError,'action cap'):
                    run(task,'quoted',d,Repeater(task),max_answer_calls=3)
            state=json.loads((Path(d)/'answer-session.json').read_text())
            self.assertEqual(state['calls'],3)
            self.assertEqual(state['retrievals'],1)
            self.assertEqual(state['answers'],{'current-0':12})
            self.assertFalse((Path(d)/'result.json').exists())

    def test_transport_failure_reserves_call_before_dispatch(self):
        task=make_task(7,4,0)
        class Broken(StubClient):
            def __call__(self,messages,phase,batch_id):
                if phase=='answer':raise OSError('lost connection')
                return super().__call__(messages,phase,batch_id)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(OSError):run(task,'quoted',d,Broken(task))
            state=json.loads((Path(d)/'answer-session.json').read_text())
            self.assertEqual(state['calls'],1)
            result=run(task,'quoted',d,StubClient(task))
            self.assertEqual(result['answer_protocol']['calls'],2)
            self.assertFalse(result['timing_complete'])

    def test_invalid_json_feedback_is_bounded(self):
        task=make_task(7,4,0)
        class Invalid(StubClient):
            def __call__(self,messages,phase,batch_id):
                if phase=='answer':return 'invalid-json',{}
                return super().__call__(messages,phase,batch_id)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'action cap'):
                run(task,'quoted',d,Invalid(task),max_answer_calls=2)
            state=json.loads((Path(d)/'answer-session.json').read_text())
            self.assertEqual(state['calls'],2)
            self.assertIn('error',state['feedback'])


class PromptBudgetTests(unittest.TestCase):
    def test_newest_and_repeated_evidence_survive_expendable_memory(self):
        task = make_task(7, 4, 700)
        test = self

        class Client(StubClient):
            answer_calls = 0

            def __call__(self, messages, phase, batch_id):
                if phase == 'archive':
                    return json.dumps({'state': self.task['oracle']['after_batch'][batch_id-1],
                                       'memory': 'm' * 2300}), {}
                if phase == 'answer':
                    self.answer_calls += 1
                    payload = json.loads(messages[-1]['content'])
                    if self.answer_calls > 1:
                        expected_batch = (1, 2, 1)[self.answer_calls-2]
                        test.assertEqual(payload['retrieved'][-1]['batch_id'], expected_batch)
                        test.assertEqual(payload['retrieved'][-1]['text'],
                                         task['batches'][expected_batch-1]['text'])
                        test.assertEqual(payload['memory'], '')
                        test.assertEqual(payload['saved_answers'], {'current-0': 12})
                        test.assertEqual(payload['questions'], task['questions'])
                    if self.answer_calls <= 3:
                        return json.dumps({'action': 'fetch', 'batch_id': (1, 2, 1)[self.answer_calls-1],
                                           'answers': {'current-0': 12}}), {}
                return super().__call__(messages, phase, batch_id)

        with tempfile.TemporaryDirectory() as directory:
            result = run(task, 'archive', directory, Client(task), limit=12000)
            self.assertEqual(result['answer_protocol'], {'calls': 4, 'retrievals': 2})
            self.assertLessEqual(result['peak_prompt_bytes'], 12000)
            session = json.loads((Path(directory)/'answer-session.json').read_text())
            self.assertEqual(session['cache']['fetch:1']['text'], task['batches'][0]['text'])
            checkpoint = json.loads((Path(directory)/'checkpoint.json').read_text())
            self.assertEqual(checkpoint['memory'], 'm' * 2300)

    def test_oversize_evidence_is_reported_and_narrower_search_recovers(self):
        task = make_task(7, 4, 1100)
        test = self

        class Client(StubClient):
            answer_calls = 0

            def __call__(self, messages, phase, batch_id):
                if phase == 'archive':
                    return json.dumps({'state': self.task['oracle']['after_batch'][batch_id-1],
                                       'memory': 'm' * 2300}), {}
                if phase == 'answer':
                    self.answer_calls += 1
                    payload = json.loads(messages[-1]['content'])
                    if self.answer_calls == 1:
                        return json.dumps({'action': 'fetch', 'batch_id': 1,
                                           'answers': {'current-0': 12}}), {}
                    if self.answer_calls == 2:
                        test.assertEqual(payload['saved_answers'], {'current-0': 12})
                        test.assertEqual(payload['retrieved'][0]['batch_id'], 1)
                        test.assertIn('exceeds available prompt bytes', payload['retrieved'][0]['error'])
                        return json.dumps({'action': 'search', 'query': 'delivery seal for batch 1'}), {}
                    test.assertEqual(payload['retrieved'][-1]['total_matches'], 1)
                    test.assertEqual(payload['retrieved'][-1]['matches'][0]['batch_id'], 1)
                return super().__call__(messages, phase, batch_id)

        with tempfile.TemporaryDirectory() as directory:
            result = run(task, 'archive', directory, Client(task), limit=12000)
            self.assertEqual(result['answer_protocol'], {'calls': 3, 'retrievals': 2})
            self.assertLessEqual(result['peak_prompt_bytes'], 12000)
            session = json.loads((Path(directory)/'answer-session.json').read_text())
            self.assertEqual(session['cache']['fetch:1']['text'], task['batches'][0]['text'])
            self.assertFalse(session['cache']['fetch:1']['truncated'])

if __name__=='__main__':unittest.main()
