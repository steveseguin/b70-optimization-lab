import itertools
import json
from pathlib import Path
import random
import unittest

import placement


def fixture(sizes=(11, 40, 7, 31, 3, 20)):
    rows, offset = [], 0
    for layer, size in enumerate(sizes):
        # Distinct quant IDs deliberately need no hardcoded model-specific table.
        rows.append(f'a.gguf blk.{layer}.weight dense {layer + 8} {offset} {size} {layer} 1 2 8 16')
        offset += size
    rows += [f'a.gguf output.weight target_head 14 {offset} 13 -1 2 2 8 16',
             'b.gguf per_layer_token_embd.weight ple_lookup 20 0 1000000 1 0 2 8 16',
             'c.gguf token_embd.weight embedding 23 0 17 -1 0 2 8 16']
    return ('\n'.join(rows) + '\n').encode()


class PartitionTests(unittest.TestCase):
    def test_minimax_matches_exhaustive_partitions(self):
        randomizer = random.Random(123)
        for length in range(1, 9):
            for count in range(1, length + 1):
                costs = [randomizer.randrange(0, 100) for _ in range(length)]
                overhead = [randomizer.randrange(0, 30) for _ in range(count)]
                expected = min(max(sum(costs[a:b]) + overhead[rank]
                                   for rank, (a, b) in enumerate(zip((0,) + cuts, cuts + (length,))))
                               for cuts in itertools.combinations(range(1, length), count - 1))
                actual, ranges = placement.partition(costs, count, overhead)
                self.assertEqual(actual, expected)
                self.assertEqual([i for a, b in ranges for i in range(a, b)], list(range(length)))

    def test_invalid_counts_and_costs(self):
        for count in (0, -1, 4, True):
            with self.assertRaises(ValueError):
                placement.partition([1, 2, 3], count)
        for costs in ([1, -1], [1, 0.1], [True, 2]):
            with self.assertRaises(ValueError):
                placement.partition(costs, 1)
        with self.assertRaises(ValueError):
            placement.partition([1, 2, 3], 2, [0])

    def test_all_tensor_bytes_accounted_for(self):
        result = placement.plan(fixture(), 'different-model-and-quants', [1, 2, 4, 6])
        for proposal in result['proposals']:
            self.assertEqual(sum(stage['packed_bytes'] for stage in proposal['stages']), 112)
            self.assertEqual(sum(stage['tensors'] for stage in proposal['stages']), 6)
        excluded = result['excluded_lookup_tensors'] + result['excluded_global_tensors']
        self.assertEqual(sum(t['bytes'] for t in excluded) + result['layer_inventory']['packed_bytes'],
                         result['input_inventory']['packed_bytes'])
        self.assertFalse(result['executable'])
        self.assertEqual(result['placement_sha256'], placement.sha(fixture()))
        self.assertEqual(result['objective'], 'packed_layer_weight_bytes')
        self.assertEqual(len(result['layer_inventory']['quantization_types']), 6)

    def test_profile_changes_partition_and_records_identity(self):
        data = fixture((10, 10, 10, 10, 10, 10))
        profile = dict(schema='ownrt.pipeline.layer-costs.v1', placement_sha256=placement.sha(data),
                       runtime_sha256='1' * 64, measurement_sha256='2' * 64,
                       run_identity={'activations': 'f32', 'context': 4096, 'workload': 'test'},
                       layer_ns=[1, 1, 1, 1, 1, 1], stage_overhead_ns={'2': [4, 0]})
        raw = json.dumps(profile).encode()
        result = placement.plan(data, 'test', [2], raw)
        self.assertEqual(result['proposals'][0]['stages'][0]['layer_end_exclusive'], 1)
        self.assertEqual(result['proposals'][0]['maximum_stage_cost'], 5)
        self.assertEqual(result['cost_profile_sha256'], placement.sha(raw))
        self.assertEqual(result['objective'], 'measured_layer_ns')
        self.assertEqual(result['proposals'][0]['overhead_status'], 'supplied')
        for key, value in [('placement_sha256', '3' * 64), ('runtime_sha256', 'missing'),
                           ('measurement_sha256', None), ('layer_ns', [1]), ('run_identity', {})]:
            broken = dict(profile, **{key: value})
            with self.assertRaises(ValueError, msg=key):
                placement.plan(data, 'test', [2], json.dumps(broken).encode())

    def test_structural_rejections(self):
        original = fixture().decode()
        mutations = [original + original.splitlines()[0] + '\n',
                     original.replace('dense 8 0 11', 'dense 8 0 -11'),
                     original.replace('dense 9 11 40', 'dense 9 1 40'),
                     original.replace('0 1 2 8 16', '0 1 3 8 16', 1),
                     original.replace('blk.0.weight', 'blk.8.weight'),
                     original.replace('2 8 16', '2 0 16', 1), '']
        for data in mutations:
            with self.assertRaises(ValueError, msg=data[:80]):
                placement.parse_placement(data.encode())
        with self.assertRaises(ValueError):
            placement.plan(fixture(), 'test', [2, 2])

    def test_real_sc117_metadata_without_model_access(self):
        source = Path(__file__).resolve().parents[2] / 'gsq-rco-iq3s/loader/placement.tsv'
        result = placement.plan(source.read_bytes(), 'SC117', [1, 2, 4, 6])
        self.assertEqual(result['proposals'][0]['stages'][0]['layer_end_exclusive'], 48)
        self.assertEqual(sum(t['bytes'] for t in result['excluded_lookup_tensors']), 29137853440)
        for proposal in result['proposals']:
            self.assertEqual(sum(s['packed_bytes'] for s in proposal['stages']), result['layer_inventory']['packed_bytes'])


if __name__ == '__main__':
    unittest.main()
