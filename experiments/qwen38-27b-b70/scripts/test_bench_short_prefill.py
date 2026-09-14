import importlib.util
import json
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('prefill', Path(__file__).with_name('bench-short-prefill.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class StreamTests(unittest.TestCase):
    def events(self):
        return [
            {'elapsed_s': .2, 'data': json.dumps({'choices': [{'token_ids': list(range(4))}]})},
            {'elapsed_s': 1.2, 'data': json.dumps({'choices': [{'token_ids': list(range(4, 100))}]})},
            {'elapsed_s': 1.5, 'data': json.dumps({'choices': [{'token_ids': list(range(100, 128))}]})},
            {'elapsed_s': 1.6, 'data': json.dumps({'choices': [], 'usage': {'prompt_tokens': 512, 'completion_tokens': 128, 'prompt_tokens_details': {'cached_tokens': 0}}})},
            {'elapsed_s': 1.6, 'data': '[DONE]'}]

    def test_bursts_use_numeric_token_intervals(self):
        row = m.parse_events(self.events(), 512, 128)
        self.assertEqual(row['decode_token_1_to_100_tps'], 99)
        self.assertAlmostEqual(row['decode_after_ttft_tps'], 127 / 1.3)
        self.assertEqual(row['token_offsets_s'][:4], [.2] * 4)
        self.assertEqual(row['http_prompt_tokens_per_ttft_s'], 2560)

    def test_missing_ids_usage_done_and_cache_fail_closed(self):
        for mutation in ('ids', 'usage', 'done', 'cache', 'unknown_cache', 'wrong_prompt'):
            with self.subTest(mutation=mutation):
                events = self.events()
                if mutation == 'ids': events.pop(0)
                elif mutation == 'done': events.pop()
                else:
                    event = json.loads(events[3]['data'])
                    if mutation == 'usage': event.pop('usage')
                    elif mutation == 'cache': event['usage']['prompt_tokens_details']['cached_tokens'] = 1
                    elif mutation == 'unknown_cache': event['usage'].pop('prompt_tokens_details')
                    else: event['usage']['prompt_tokens'] = 511
                    events[3]['data'] = json.dumps(event)
                with self.assertRaises(ValueError): m.parse_events(events, 512, 128)

    def test_server_error_rejected(self):
        with self.assertRaises(ValueError):
            m.parse_events([{'elapsed_s': 0, 'data': '{"error":"failed"}'}], 512, 128)

    def test_metric_delta_separates_prefill_and_http(self):
        before = 'vllm:request_prefill_time_seconds_sum{model="x"} 2\nvllm:request_prefill_time_seconds_count{model="x"} 4\nvllm:prompt_tokens_total{model="x"} 1024\n'
        after = before.replace('} 2\n', '} 2.25\n').replace('} 4\n', '} 5\n').replace('} 1024\n', '} 1536\n')
        row = m.metric_delta(before, after, 512)
        self.assertEqual(row['server_prefill_s'], .25)
        self.assertEqual(row['server_prefill_tokens_per_s'], 2048)
        with self.assertRaises(ValueError): m.metric_delta(before, after.replace('} 5\n', '} 6\n'), 512)
        with self.assertRaises(ValueError): m.metric_delta(before, after.replace('} 1536\n', '} 1500\n'), 512)

    def test_missing_metric_is_not_fabricated(self):
        self.assertIsNone(m.metric_delta('# no histogram', '# no histogram', 512)['server_prefill_s'])

if __name__ == '__main__': unittest.main()
