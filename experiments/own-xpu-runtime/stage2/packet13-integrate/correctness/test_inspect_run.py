import unittest
from inspect_run import classify


class TokenProvenance(unittest.TestCase):
    def test_prompt_tokens_are_not_generated_output(self):
        prompt = [248045, 846, 198, 2523]
        rows = [dict(kind='token', token_index=i, input_token=t) for i,t in enumerate(prompt[:3])]
        result = classify(prompt, rows, [])
        self.assertTrue(result['observed_prefill_matches_prompt'])
        self.assertFalse(result['generation_established'])
        self.assertFalse(result['prefill_complete'])

    def test_complete_prefill_alone_does_not_establish_generated_text(self):
        self.assertFalse(classify([1], [dict(kind='token',token_index=0,input_token=1)], [])['generation_established'])

    def test_generated_ids_come_from_output_record(self):
        rows = [dict(kind='token',token_index=0,input_token=1), dict(kind='token',token_index=1,input_token=332)]
        result = classify([1], rows, [332,37947])
        self.assertTrue(result['prefill_complete'])
        self.assertEqual(result['generated_tokens'], [332,37947])

    def test_prompt_mismatch_is_not_hidden(self):
        self.assertFalse(classify([1], [dict(kind='token',token_index=0,input_token=2)], [])['observed_prefill_matches_prompt'])


if __name__ == '__main__':
    unittest.main()
