"""Read-only authority checks for the retained synthetic CPU cache proof.
No native executable is invoked; expected bytes are derived without candidate code.
"""
import hashlib
import json
import struct
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[3]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chronological_routes(round_index):
    return [layer * 4 + (layer + round_index + row + slot) % 4
            for row in range(2) for layer in range(48) for slot in range(2)]


def expected_output(round_index):
    result = bytearray()
    for row in range(2):
        for layer in range(48):
            for slot in range(2):
                expert = (layer + round_index + row + slot) % 4
                for projection in range(3):
                    result.extend(((layer * 37 + expert * 59 + projection * 83 + j * 11)
                                   ^ (j * layer + expert)) & 255 for j in range(32))
    return bytes(result)


def final_residents(round_index):
    # Eight equal-size aligned cache slots; the most recent eight distinct IDs
    # follow directly from the declared chronological LRU policy.
    newest = []
    for expert in reversed(chronological_routes(round_index)):
        if expert not in newest:
            newest.append(expert)
        if len(newest) == 8:
            return sorted(newest)
    raise AssertionError("fixture does not force eviction")


class SourceAuthority(unittest.TestCase):
    def test_pinned_inherited_sources_and_objects(self):
        authority = read(P / 'authority-inputs.json')
        for group in ('source_sha256', 'parent_host_object_lineage'):
            for path, expected in authority[group].items():
                with self.subTest(path=path):
                    self.assertEqual(sha(ROOT / path), expected)

    def test_backend_and_publication_are_original_inherited_implementations(self):
        authority = read(P / 'authority-inputs.json')
        self.assertIn('simulated', authority['completion_scope'])
        self.assertEqual(authority['geometry'], dict(layers=48, experts_per_layer=4,
                                                   projections=3, projection_bytes=32, tables=144))
        self.assertFalse(authority['native_or_model_executed'])
        source = (P / 'cache_probe.cpp').read_text()
        self.assertIn('#include "../packet205-host-row-capture/host_backend.hpp"', source)
        self.assertIn('/native/publish.hpp"', source)
        self.assertIn('/native/cache_table.hpp"', source)


class RetainedProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = read(P / 'evidence/host-cache.json')
        cls.build = read(P / 'evidence/build.json')

    def checks(self, *names):
        for name in names:
            with self.subTest(check=name):
                self.assertIs(self.result['checks'][name], True)

    def test_compiler_binary_and_inherited_object_closure(self):
        self.assertIs(self.build['passed'], True)
        self.assertIs(self.result['passed'], True)
        self.assertEqual(self.result['build_receipt_sha256'], sha(P / 'evidence/build.json'))
        self.assertEqual(self.result['source_sha256'], self.build['source_sha256'])
        self.assertEqual(self.result['binary_sha256'], self.build['binary_sha256'])
        self.assertEqual(sha(ROOT / self.build['binary']), self.build['binary_sha256'])
        for path, expected in self.build['source_sha256'].items():
            with self.subTest(source=path):
                self.assertEqual(sha(ROOT / path), expected)
        parent = read(P.parent / 'packet198-postreply-checkpoint/evidence/build-compile-only.json')
        objects = next(row['objects'] for row in parent['plans'] if row['target'] == 'host')
        for path, expected in self.build['reused_host_object_sha256'].items():
            with self.subTest(object=path):
                self.assertEqual(expected, objects[path])
                self.assertEqual(sha(Path(path)), expected)

    def test_explicit_synthetic_cpu_and_matched_policy_scope(self):
        self.assertEqual(self.result['schema'], 'packet210.host-cache-proof.v1')
        self.assertIs(self.result['device_executed'], False)
        self.assertIs(self.result['model_executed'], False)
        self.assertIn('simulated', self.result['completion_scope'])
        self.assertIn('not production expert arithmetic', self.result['arithmetic_scope'])
        self.assertIn('chronological single-touch', self.result['policy'])
        self.assertEqual(self.result['geometry'], dict(layers=48, experts=4, projections=3,
                                                      payload_bytes=32, top=2, cache_bytes=2048,
                                                      route_bytes=12, route_row_begin="row*2+slot", route_row_count=1))

    def test_all_consumer_bytes_match_independent_python_formula(self):
        rows = self.result['intervals']
        self.assertEqual([row['round'] for row in rows], [0, 1, 2])
        for row in rows:
            expected = expected_output(row['round'])
            with self.subTest(round=row['round']):
                self.assertEqual(row['output_bytes'], len(expected))
                self.assertEqual(row['output_sha256'], hashlib.sha256(expected).hexdigest())
                self.assertEqual(row['expected_sha256'], row['output_sha256'])
        self.assertEqual(len({row['output_sha256'] for row in rows}), 3)
        self.checks('independent_payload_formula_and_schedules_exact',
                    'normalized_identity_payload_generation_exact')

    def test_chronological_retention_and_lru_residents(self):
        for row in self.result['intervals']:
            with self.subTest(round=row['round']):
                self.assertEqual(row['routes'], chronological_routes(row['round']))
                raw_routes = b''.join(struct.pack('<III', (layer + row['round'] + r + slot) % 4,
                                                  r * 2 + slot, 1)
                                      for r in range(2) for layer in range(48) for slot in range(2))
                self.assertEqual(row['route_log_sha256'], hashlib.sha256(raw_routes).hexdigest())
                self.assertEqual(row['resident_ids'], final_residents(row['round']))
                self.assertEqual(row['hits'] + row['misses'], 2 * 48 * 2)
        self.assertEqual(self.result['intervals'][0]['hits'], 0)
        self.assertGreater(sum(row['hits'] for row in self.result['intervals'][1:]), 0)
        self.assertGreater(sum(row['misses'] for row in self.result['intervals']), 0)
        self.checks('both_cache_hits_and_pinned_misses_consumed',
                    'wrong_layer_major_replay_changes_residency', 'wrong_replay_changes_normalized_table')
        h = self.result['byte_sha256']
        self.assertNotEqual(h['correct_replay_normalized'], h['wrong_replay_normalized'])

    def test_captured_handles_live_payloads_and_indirect_ownership(self):
        self.checks('publication_capture_has_145_owned_device_ids',
                    'captured_table_ids_ignore_caller_rebinding',
                    'caller_destination_decoys_untouched',
                    'live_staging_updates_fixed_table_handles',
                    'captured_consumer_reads_live_table_bytes',
                    'released_indirect_pinned_payload_refuses_capture',
                    'pending_publication_retains_hidden_pinned_staging',
                    'pending_publication_refuses_staging_overwrite')
        h = self.result['byte_sha256']
        self.assertNotEqual(h['changed_table_output'], h['expected_table_output'])

    def test_frozen_readers_and_incomplete_completion_refuse_maintenance(self):
        self.checks('frozen_table_and_victim_bytes_both_rows',
                    'publish_during_read_refused', 'cache_prepare_during_read_refused',
                    'late_old_table_consumer_refused',
                    'incomplete_consumer_prevents_finish_and_publication',
                    'incomplete_consumer_retains_payloads')

    def test_partial_writes_poison_without_rollback_or_next_chunk(self):
        self.checks('partial_fill_fault_injected', 'partial_fill_overwrites_populated_victim',
                    'partial_fill_poison_no_rollback_or_next_chunk',
                    'partial_publication_fault_injected', 'partial_publication_changes_some_not_all_tables',
                    'partial_publication_poison_no_rollback_or_next_chunk')


    def test_partial_write_evidence_preserves_exact_first_errors(self):
        self.assertEqual(self.result['first_errors'],
                         dict(partial_fill='copy extent/lifetime', partial_publication='copy extent/lifetime'))
        h = self.result['byte_sha256']
        self.assertNotEqual(h['before_partial_fill_slots'], h['partial_fill_slots'])
        self.assertEqual(h['before_partial_fill_tables'], h['after_partial_fill_tables'])
        self.assertNotEqual(h['partial_publication_tables'], h['before_partial_publication_tables'])
        self.assertNotEqual(h['partial_publication_tables'], h['intended_publication_tables'])

    def test_every_owner_is_drained_without_turning_failed_transactions_into_success(self):
        receipts = self.result['owner_receipts']
        self.assertEqual(set(receipts), {'serial', 'chunk', 'correct_replay', 'wrong_replay',
                                        'live_table_mutation', 'stale_indirect', 'pending_staging',
                                        'incomplete_consumer', 'partial_fill', 'partial_publication'})
        for name, row in receipts.items():
            with self.subTest(owner=name):
                self.assertEqual(row['backend'], 'MockDevice')
                self.assertIs(row['safe_to_exit'], True)
                self.assertIs(row['idle_marker_complete'], True)
                self.assertEqual(row['in_flight'], 0)
                self.assertEqual(row['live_bytes'], 0)
                self.assertEqual(row['sequence'][-4:], ['idle-marker-complete', 'events-released',
                                                       'queue-released', 'context-released'])
                # Copy extent refusals precede backend submission. A clean owner
                # shutdown is possible while the separately recorded transaction failed.
                self.assertEqual(row['exit_code'], 0)
        for failure in ('partial_fill', 'partial_publication'):
            self.assertEqual(self.result['first_errors'][failure], 'copy extent/lifetime')


if __name__ == '__main__':
    unittest.main()
