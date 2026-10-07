import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tasks import make_task, verify
from pilot import run, StubClient, grade, HTTPClient

class PilotTests(unittest.TestCase):
    def test_generator_fixed_question_counts_and_hash(self):
        task=make_task(101,8,30,'dispatch');verify(task)
        self.assertEqual(task,make_task(101,8,30,'dispatch'))
        self.assertEqual(grade(task,task['oracle']['answers'])['by_category'],{k:{'correct':8,'asked':8} for k in ('current','history','join')})
        task['batches'][0]['text']+=' forged'
        with self.assertRaises(ValueError):verify(task)

    def test_stub_all_arms_bounded_and_labelled(self):
        task=make_task(7,12,150)
        for arm in ('summary','archive','quoted'):
            with self.subTest(arm=arm),tempfile.TemporaryDirectory() as d:
                result=run(task,arm,Path(d),StubClient(task),12000)
                self.assertEqual(result['score']['correct'],24)
                self.assertEqual(result['measurement_kind'],'stub')
                self.assertLessEqual(result['peak_prompt_bytes'],12000)
                self.assertIsNone(result['generated_tokens'])
                if arm=='summary':
                    calls=[json.loads(l) for l in (Path(d)/'calls.jsonl').read_text().splitlines()]
                    self.assertTrue(any(c['phase']=='summary' for c in calls))

    def test_restart_does_not_reapply(self):
        task=make_task(7,6,10)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            self.assertEqual(run(task,'quoted',out,StubClient(task),stop_after=3)['status'],'interrupted')
            before=len((out/'calls.jsonl').read_text().splitlines())
            result=run(task,'quoted',out,StubClient(task))
            self.assertEqual(result['score']['correct'],24)
            self.assertTrue(result['resumed']);self.assertFalse(result['timing_complete'])
            self.assertEqual(result['calls'],before+4)

    def test_crash_after_apply_before_checkpoint(self):
        import pilot
        task=make_task(7,5,0)
        original=pilot.atomic
        def crash(path,value):
            if path.name=='checkpoint.json':raise RuntimeError('simulated process loss after commit')
            original(path,value)
        with tempfile.TemporaryDirectory() as d:
            with patch('pilot.atomic',side_effect=crash):
                with self.assertRaises(RuntimeError):run(task,'quoted',Path(d),StubClient(task))
            result=run(task,'quoted',Path(d),StubClient(task))
            self.assertEqual(result['score']['correct'],24)
            self.assertEqual(result['calls'],6)
            self.assertEqual(len(result['state_checks']),5)

    def test_identity_change_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            task=make_task(7,4,0)
            run(task,'quoted',Path(d),StubClient(task),stop_after=1)
            with self.assertRaises(ValueError):run(task,'archive',Path(d),StubClient(task))

    def test_wrong_extra_bool_answers_not_success(self):
        task=make_task(7,4,0)
        answers=dict(task['oracle']['answers']);answers['current-0']=True;answers['invented']=0
        result=grade(task,answers)
        self.assertFalse(result['valid']);self.assertEqual(result['correct'],23)

    def test_request_failure_saved(self):
        class Broken:
            kind='stub'
            def __call__(self,*a):raise OSError('test connection loss')
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(OSError):run(make_task(7,4,0),'quoted',Path(d),Broken())
            calls=(Path(d)/'calls.jsonl').read_text()
            self.assertIn('test connection loss',calls)
            self.assertFalse((Path(d)/'result.json').exists())

    def test_real_prompt_never_contains_hidden_answer_key(self):
        task=make_task(7,4,0)
        class Observer(StubClient):
            kind='stub'
            def __call__(self,messages,phase,batch_id):
                text=json.dumps(messages)
                assert '"oracle"' not in text and '"after_batch"' not in text
                return super().__call__(messages,phase,batch_id)
        with tempfile.TemporaryDirectory() as d:run(task,'quoted',Path(d),Observer(task))

    def test_remote_endpoint_rejected(self):
        with self.assertRaises(ValueError):HTTPClient('https://example.com/v1','model')


class RecoveryTests(unittest.TestCase):
    def test_torn_log_preserved_then_resumed(self):
        task=make_task(7,4,0)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);run(task,'quoted',out,StubClient(task),stop_after=1)
            with (out/'calls.jsonl').open('ab') as f:f.write(b'{"phase":')
            result=run(task,'quoted',out,StubClient(task))
            self.assertEqual(result['score']['correct'],24)
            self.assertEqual(next(out.glob('calls.jsonl.partial-*')).read_bytes(),b'{"phase":')

    def test_complete_corrupt_log_refused(self):
        from pilot import recover_log
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'calls.jsonl';path.write_text('bad\n')
            with self.assertRaises(ValueError):recover_log(path)
            self.assertEqual(path.read_text(),'bad\n')

    def test_retrieval_mistake_can_be_corrected(self):
        task=make_task(7,4,0)
        class Retriever(StubClient):
            step=0
            def __call__(self,messages,phase,batch_id):
                if phase=='answer':
                    self.step+=1
                    if self.step==1:return '{"batch":999}',{}
                    if self.step==2:
                        assert 'error' in messages[-1]['content']
                        return '{"search":"ticket-7-0"}',{}
                return super().__call__(messages,phase,batch_id)
        with tempfile.TemporaryDirectory() as d:
            result=run(task,'quoted',Path(d),Retriever(task))
            self.assertEqual(result['score']['correct'],24)
            self.assertEqual(len((Path(d)/'retrieval.jsonl').read_text().splitlines()),2)

    def test_missing_usage_stays_unknown(self):
        task=make_task(7,4,0)
        class MissingUsage(StubClient):kind='model'
        with tempfile.TemporaryDirectory() as d:
            result=run(task,'quoted',Path(d),MissingUsage(task))
            self.assertIsNone(result['generated_tokens']);self.assertIsNone(result['peak_model_prompt_tokens'])
            self.assertFalse(result['usage_complete'])

if __name__=='__main__':
    unittest.main()
