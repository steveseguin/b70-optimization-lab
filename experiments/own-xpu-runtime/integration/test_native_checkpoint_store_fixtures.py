"""Replay retained real p198 metadata only; no native tool or original blob access."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from checkpoint_bridge import BridgeRefusal, validate_snapshot


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'checkpoint-fixtures-p198'


def load(name): return json.loads((FIXTURES / name).read_text())


def arguments(checkpoint_id):
    payloads = load(checkpoint_id + '.small-payloads.json')
    return dict(checkpoint_id=checkpoint_id, inspect_returncode=0,
                inspect_stdout=(FIXTURES / (checkpoint_id + '.inspect.json')).read_bytes(),
                manifest_bytes=(FIXTURES / (checkpoint_id + '.manifest.json')).read_bytes(),
                tokens_bytes=bytes.fromhex(payloads['tokens.bin']), next_token_bytes=bytes.fromhex(payloads['next_token.bin']),
                expected_identity=load('admitted-engine-identity.json'), admitted_contract='v1.2+p198')


class ActualMetadataFixtures(unittest.TestCase):
    def test_every_captured_byte_matches_provenance(self):
        provenance = load('provenance.json')
        self.assertTrue(provenance['passed']); self.assertIs(provenance['device_executed'], False)
        for name, digest in provenance['files_sha256'].items():
            path = FIXTURES / name
            self.assertTrue(path.resolve().is_relative_to(FIXTURES.resolve()))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)
        receipt = json.loads((HERE / 'receipts/native-checkpoint-store-tools-20261023.json').read_text())
        self.assertTrue(receipt['passed'])
        self.assertEqual(receipt['fixture_provenance_sha256'], hashlib.sha256((FIXTURES / 'provenance.json').read_bytes()).hexdigest())
        self.assertFalse(receipt['device_executed']); self.assertFalse(receipt['model_executed'])
        self.assertEqual(receipt['native_model_owners_started'], 0)
        self.assertEqual(receipt['delete_statuses'], ['in_use','ok','missing'])

    def test_real_s1_and_s3_raw_identity_and_small_payloads(self):
        for checkpoint_id, n, pending, storage in (('s1',342,37574,69121547), ('s3',596,11,76342000)):
            with self.subTest(checkpoint_id=checkpoint_id):
                args = arguments(checkpoint_id); view = validate_snapshot(**args)
                self.assertEqual((len(view.processed_tokens),view.pending_token), (n,pending))
                self.assertEqual(view.manifest_bytes, args['manifest_bytes'])
                self.assertEqual(view.native_inspect_mode, 'metadata')
                recorded = load('provenance.json')['snapshots'][checkpoint_id]
                self.assertEqual(view.manifest_sha256, recorded['manifest_sha256'])
                self.assertEqual(recorded['storage_bytes'], storage)
                self.assertFalse(recorded['full_state_revalidated_by_probe'])
                inspected = json.loads(args['inspect_stdout'])
                for key in ('tokens','semantic_blob_checks','blobs_verified','blob_bytes_verified'):
                    self.assertIsNone(inspected['verified'][key])

    def test_actual_saved_history_is_prefix_of_canonical_append(self):
        s1 = validate_snapshot(**arguments('s1')); s3 = validate_snapshot(**arguments('s3'))
        appended = s3.processed_tokens[:469]
        self.assertEqual(appended[:343], s1.saved_history)
        plan = s1.plan_append(appended, max_new=128)
        self.assertEqual((plan.processed_tokens,plan.saved_history_tokens,plan.delta_tokens,plan.native_prefill_tokens),
                         (342,343,126,127))
        parent = json.loads(s3.manifest_bytes)['lineage']['parent']
        self.assertEqual(parent['checkpoint_id'], 's1'); self.assertEqual(parent['manifest_sha256'], s1.manifest_sha256)

    def test_tool_binary_is_not_the_checkpoint_engine_or_adapter_proof(self):
        provenance = load('provenance.json'); args = arguments('s1')
        self.assertNotEqual(provenance['host_tool_binary_sha256'], provenance['admitted_device_binary_sha256'])
        self.assertEqual(args['expected_identity']['engine']['binary_sha256'], provenance['admitted_device_binary_sha256'])
        wrong = copy.deepcopy(args)
        wrong['expected_identity']['engine']['binary_sha256'] = provenance['host_tool_binary_sha256']
        with self.assertRaises(BridgeRefusal): validate_snapshot(**wrong)
        legacy = dict(args); legacy.pop('admitted_contract')
        with self.assertRaises(BridgeRefusal): validate_snapshot(**legacy)
        view = validate_snapshot(**args).parking_metadata()
        self.assertEqual(view['label'], 'experimental-postreply-front')
        self.assertFalse(view['bridge']['full_state_revalidated_by_bridge'])

    def test_actual_tool_calls_are_bounded_metadata_and_scratch_deletion(self):
        calls = load('provenance.json')['native_tool_calls']
        self.assertEqual(len(calls), 5)
        self.assertEqual([row['returncode'] for row in calls], [0,0,0,1,0])
        self.assertEqual([row['argv'][1] for row in calls],
                         ['--checkpoint-inspect-metadata']*3 + ['--checkpoint-delete']*2)
        for row in calls:
            self.assertEqual(len(row['argv']), 3)
        for row in calls[3:]:
            self.assertIn('/.native-checkpoint-store-probe/20261023-a/checkpoints/s1', row['argv'][2])
            self.assertNotIn('/evidence/device-p198-', row['argv'][2])


if __name__ == '__main__': unittest.main()
