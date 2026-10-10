"""Pure CPU preflight tests: no server, process, socket, or device calls."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

client = module('ltx_client_preflight', ROOT / 'stream/ltx_continuation_client.py')
contract = module('ltx_118b_contract', ROOT / 'recovery/20261009-continuation118b-stream/stream_contract.py')


class Preflight118b(unittest.TestCase):
    def setUp(self):
        self.client = client.Client.__new__(client.Client)
        self.client.c = contract
        self.client.a = SimpleNamespace(packet='118b', manifest_sha256='a' * 64,
            expect_frames=121, expect_placement='two-way20-28', expect_text_reuse=1,
            expect_anchor='frame', expect_decoder_graph=0, expect_anchor_decode='cone',
            expect_bencode_overlap=1, expect_prep_ahead=1, expect_snapshot_mode='fingerprint',
            expect_pool_cap_bytes=None, expect_pool_cap_gb='none')
        self.bound = []
        self.client.bind_dirs = self.bound.append
        self.status = dict(packet='118b', runtime_manifest_sha256='a' * 64,
            server_identity_sha256='b' * 64, receipt_dir='/unused-cpu-receipts', frames=121,
            placement='two-way20-28', text_reuse=1, anchor='frame', decoder_graph=0,
            anchor_decode='cone', bencode_overlap=1, prep_ahead=1,
            snapshot_mode='fingerprint', decoder_graph_pool_cap_bytes=None,
            phase='stream', features=dict(decode_thread=True, async_preview=True,
                chain_reset=True, chunk_length_choice=True, sharpness_diagnostic=True,
                video_first_handoff=True, frame_anchor=True, mixed_anchor=False,
                latent_anchor=False, guide_anchor=False, decoder_graph=False,
                cone_anchor_decode=True, bencode_overlap=True, prep_ahead=True,
                chunk_121=True, timing_split=True, snapshot_fingerprint=True,
                decoder_graph_pool_cap=False))
        self.status['qualification_id'] = contract.qualification_id(121, 'two-way20-28', 'frame', 0,
                                                                     'cone', 1, 1)

    def refuse(self):
        with self.assertRaises(client.Stop) as caught:
            self.client.preflight(self.status)
        self.assertEqual(caught.exception.code, 8)
        self.assertEqual(self.bound, [])

    def test_recommended_first_launch(self):
        self.client.preflight(self.status)
        self.assertEqual(self.bound, [self.status])

    def test_withdrawn_packet_refused(self):
        self.status['packet'] = 118
        self.refuse()

    def test_wrong_manifest_refused(self):
        self.status['runtime_manifest_sha256'] = 'c' * 64
        self.refuse()

    def test_snapshot_expectation_refused(self):
        self.status['snapshot_mode'] = 'walk'
        self.status['features']['snapshot_fingerprint'] = False
        self.refuse()

    def test_unknown_snapshot_refused(self):
        self.client.a.expect_snapshot_mode = None
        self.status['snapshot_mode'] = 'unknown'
        self.refuse()

    def test_cap_without_decoder_graph_refused(self):
        self.client.a.expect_pool_cap_gb = None
        self.status['decoder_graph_pool_cap_bytes'] = 10 ** 9
        self.status['features']['decoder_graph_pool_cap'] = True
        self.refuse()

    def test_cap_expectation_refused(self):
        self.client.a.expect_pool_cap_bytes = 10 ** 9
        self.client.a.expect_pool_cap_gb = '1.0'
        self.refuse()

    def test_missing_timing_split_refused(self):
        self.status['features']['timing_split'] = False
        self.refuse()

    def test_missing_pool_feature_refused(self):
        del self.status['features']['decoder_graph_pool_cap']
        self.refuse()

    def test_decoder_graph_1_cap_accepted(self):
        self.client.a.expect_decoder_graph = 1
        self.client.a.expect_pool_cap_bytes = 10 ** 9
        self.client.a.expect_pool_cap_gb = '1.0'
        self.status['decoder_graph'] = 1
        self.status['features']['decoder_graph'] = True
        self.status['features']['decoder_graph_pool_cap'] = True
        self.status['decoder_graph_pool_cap_bytes'] = 10 ** 9
        self.status['qualification_id'] = contract.qualification_id(121, 'two-way20-28', 'frame', 1,
                                                                     'cone', 1, 1)
        self.client.preflight(self.status)
        self.assertEqual(self.bound, [self.status])


if __name__ == '__main__':
    unittest.main()
