"""Validation regressions for externally loaded/rehashed pilot tasks; CPU only."""
import copy
import hashlib
import unittest

from tasks import encoded, make_task, verify


class TaskValidationTests(unittest.TestCase):
    def setUp(self):
        self.task=make_task(seed=7,batches=4,filler_words=0)

    def rehash(self,task):
        task['task_sha256']=hashlib.sha256(encoded({k:v for k,v in task.items() if k!='task_sha256'})).hexdigest()
        return task

    def invalid(self,change,pattern):
        task=copy.deepcopy(self.task)
        change(task)
        with self.assertRaisesRegex(ValueError,pattern):
            verify(self.rehash(task))

    def test_generated_styles_seeds_and_determinism_unchanged(self):
        for seed in (0,7,19):
            for style in ('report','dispatch'):
                task=make_task(seed=seed,batches=8,filler_words=30,style=style)
                before=encoded(task)
                verify(task)
                self.assertEqual(before,encoded(task))
                self.assertEqual(task,make_task(seed=seed,batches=8,filler_words=30,style=style))

    def test_duplicate_questions_cannot_credit_one_answer_repeatedly(self):
        self.invalid(lambda t:t.update(questions=[t['questions'][0]]*24),'unique')

    def test_equal_length_mismatched_question_answer_keys_rejected(self):
        def change(t):
            t['questions'][0]['id']='not-an-answer-key'
        self.invalid(change,'exactly match')

    def test_batch_ids_require_contiguity_and_actual_integers(self):
        for bad_id in (0,3,True,'1'):
            with self.subTest(bad_id=bad_id):
                self.invalid(lambda t:t['batches'][0].update(id=bad_id),'contiguous')

    def test_reference_and_event_batch_counts(self):
        for key in ('after_batch','events'):
            with self.subTest(key=key):
                self.invalid(lambda t:t['oracle'][key].pop(),'every batch')

    def test_types_reject_boolean_answers_and_states(self):
        self.invalid(lambda t:t['oracle']['answers'].update({'current-0':True}),'answer type')
        self.invalid(lambda t:t['oracle']['after_batch'][0].update({'amber10':True}),'integer balances')
        self.invalid(lambda t:t['questions'][0].update(question=None),'nonempty text')

    def test_duplicate_event_ids_invalid_quotes_and_amounts(self):
        self.invalid(lambda t:t['oracle']['events'][0][1].update(id=t['oracle']['events'][0][0]['id']),'globally unique')
        self.invalid(lambda t:t['oracle']['events'][0][0].update(quote='Not in the report.'),'source quote')
        self.invalid(lambda t:t['oracle']['events'][0][0].update(amount=True),'amount')

    def test_oracle_arithmetic_must_match_reference(self):
        self.invalid(lambda t:t['oracle']['after_batch'][0].update({'amber10':999}),'disagree')

    def test_hash_mismatch_and_missing_structure_are_clear_errors(self):
        task=copy.deepcopy(self.task);task['seed']=9
        with self.assertRaisesRegex(ValueError,'hash mismatch'):verify(task)
        for value in (None,[],{}, {'schema':'wrong'}):
            with self.assertRaises(ValueError):verify(value)


if __name__=='__main__':unittest.main()
