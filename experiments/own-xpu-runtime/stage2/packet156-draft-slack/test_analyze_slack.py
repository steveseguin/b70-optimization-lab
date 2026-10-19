"""Actual first-request parser failures; no mock replaces the data proof."""
import copy
import gzip
import json
from pathlib import Path
import resource
import tempfile
import unittest

import analyze_slack as method


class FirstRequestProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((method.P/'evidence/smoke-bound.json').read_text())['inputs']
        def load(entry):
            packed = (method.P/entry['retained']).read_bytes()
            method.demand(method.digest(packed) == entry['retained_sha256'], 'compressed test input hash')
            raw = gzip.decompress(packed)
            method.demand(method.digest(raw) == entry['sha256'], 'raw test input hash')
            return raw.decode()
        view = json.loads(load(next(e for e in manifest if e['source'].endswith('/bracket-inputs.json'))))['views'][0]
        cls.request = view['requests'][0]
        folder = Path(view['output'])/cls.request['prompt_id']
        cls.raw = [load(next(e for e in manifest if e['source'] == str(
            (folder/f'rank{rank}/timings.jsonl').relative_to(method.ROOT)))) for rank in (0,1)]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)/self.request['prompt_id']
        for rank in (0,1):
            path = self.path(rank)
            path.parent.mkdir(parents=True)
            path.write_text(self.raw[rank])

    def path(self, rank=1):
        return self.folder/f'rank{rank}/timings.jsonl'

    def proof(self, request=None):
        return method.request_bound(self.folder, request or self.request)

    def rows(self):
        return [json.loads(line) for line in self.path().read_text().splitlines()]

    def write_rows(self, rows):
        self.path().write_text(''.join(json.dumps(row)+'\n' for row in rows))

    def test_real_first_request(self):
        result = self.proof()
        self.assertEqual(result['fully_contained_windows'], 63)
        self.assertTrue(result['below_hit_threshold'])

    def test_delayed_first_request_has_no_wall_deadline(self):
        request = copy.deepcopy(self.request)
        request['request_start_monotonic'] -= 3600
        request['ttft_ms'] += 3_600_000
        self.assertEqual(self.proof(), self.proof(request))

    def test_missing_streams(self):
        for rank in (0,1):
            with self.subTest(rank=rank):
                self.path(rank).unlink()
                with self.assertRaisesRegex(ValueError, 'missing rank'):
                    self.proof()
                self.path(rank).write_text(self.raw[rank])

    def test_empty_streams(self):
        for rank in (0,1):
            with self.subTest(rank=rank):
                self.path(rank).write_text('')
                with self.assertRaisesRegex(ValueError, 'empty rank'):
                    self.proof()
                self.path(rank).write_text(self.raw[rank])

    def test_wrong_rank(self):
        rows = self.rows()
        for row in rows:
            if 'p154_segment' in row:
                row['rank'] = 0
                break
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, 'invalid scope clock'):
            self.proof()

    def test_truncated_stream(self):
        self.path().write_text(self.raw[1]+'{"p154_segment":')
        with self.assertRaises(json.JSONDecodeError):
            self.proof()

    def test_missing_suffix_census(self):
        self.write_rows([r for r in self.rows() if r.get('p154_segment') != 'wait_rank0_suffix'])
        with self.assertRaisesRegex(ValueError, 'incomplete rank1 scope census'):
            self.proof()

    def test_missing_one_prefix_completion(self):
        rows = self.rows()
        seq = next(r['sequence'] for r in rows if r.get('p154_segment') == 'prefix_pack')
        self.write_rows([r for r in rows if not (r.get('sequence') == seq and r.get('p154_segment') == 'b_completion')])
        with self.assertRaisesRegex(ValueError, 'missing/duplicate command-bound'):
            self.proof()

    def test_duplicate_completion(self):
        rows = self.rows()
        seq = next(r['sequence'] for r in rows if r.get('p154_segment') == 'prefix_pack')
        rows.append(copy.deepcopy(next(r for r in rows if r.get('sequence') == seq and r.get('p154_segment') == 'b_completion')))
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, 'missing/duplicate command-bound'):
            self.proof()

    def test_stale_sequence(self):
        rows = self.rows()
        next(r for r in rows if r.get('p154_segment') == 'prefix_pack')['sequence'] = -1
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, 'missing/duplicate command-bound'):
            self.proof()

    def test_illegal_scope_order(self):
        rows = self.rows()
        r = next(r for r in rows if r.get('p154_segment') == 'prefix_pack')
        r['start'] -= 1
        r['end'] -= 1
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, 'illegal prefix/suffix scope order'):
            self.proof()

    def test_nan(self):
        rows = self.rows()
        next(r for r in rows if r.get('p154_segment') == 'prefix_pack')['end'] = float('nan')
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, 'invalid scope clock'):
            self.proof()

    def test_bad_cold_gate(self):
        request = copy.deepcopy(self.request)
        request['cached_tokens'] = 1
        with self.assertRaisesRegex(ValueError, 'request quality/cold gate failed'):
            self.proof(request)

    def test_missing_token_event(self):
        request = copy.deepcopy(self.request)
        request['token_timestamps'].pop()
        with self.assertRaisesRegex(ValueError, '64 monotone timestamps required'):
            self.proof(request)


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    unittest.main()
