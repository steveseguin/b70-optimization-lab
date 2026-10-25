"""CPU fixtures prove byte, host, transport and semantic mismatch refusal."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

import compare_draft_state as compare


def fixture(root):
    root.mkdir()
    buffers = {
        'card0:draft:position': struct.pack('<i', 3),
        'card0:draft:blk.0.qsa.keys': struct.pack('<4H', 1, 2, 3, 4),
        'card0:draft:scratch': bytes(16),
        'card0:draft:publication': bytes(8),
        'card0:draft:half-staging': bytes(20),
    }
    layouts = {key: dict(bytes=len(raw), category=3, memory='device', semantic='opaque-mutable-scratch')
               for key, raw in buffers.items()}
    layouts['card0:draft:position'].update(semantic='typed-buffer', dtype='I32', shape=[1])
    layouts['card0:draft:blk.0.qsa.keys'].update(semantic='typed-buffer', dtype='BF16', shape=[2, 2])
    for key in ('card0:draft:publication', 'card0:draft:half-staging'):
        layouts[key]['memory'] = 'pinned'
    host = dict(position=3, context_extent=32, disabled=False, async_pending=False,
                pending_head=False, pending_confirmed=0, reverse_hidden_present=False,
                queued_probe=-1, queued_confirmed=-1, depth_probe=0)
    state = dict(schema='ownrt.draft-state.v1', host=host, layouts=layouts)
    manifest = dict(schema='ownrt.draft-state-set.v1', dump='dump',
                    input_identity=dict(model_sha256='a'*64, draft_model_sha256='b'*64,
                                        pair_sequence_sha256='c'*64, arithmetic='F32-target/BF16-draft', position=3))
    (root/'set.json').write_text(json.dumps(manifest))
    seal(root/'dump', buffers, state)
    return root/'set.json', buffers, state


def seal(dump, buffers, state):
    dump.mkdir(exist_ok=True)
    payload, index = bytearray(), ['GSQ_STATE_BUNDLE_V1']
    hashes = {}
    for key, raw in sorted(buffers.items()):
        hashes[key] = compare.digest(raw)
        index.append(f'{key}.bin\t{len(payload)}\t{len(raw)}\t{hashes[key]}')
        payload.extend(raw)
    state = copy.deepcopy(state)
    state['buffers'] = hashes
    meta = json.dumps(state).encode()
    index = ('\n'.join(index)+'\n').encode()
    (dump/'state.bundle').write_bytes(payload)
    (dump/'state-index.tsv').write_bytes(index)
    (dump/'state.json').write_bytes(meta)
    (dump/'state-seal.txt').write_text('\n'.join(['GSQ_STATE_SEAL_V1',str(len(payload)),
        compare.digest(payload),compare.digest(index),compare.digest(meta)])+'\n')


class DraftStateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.a, _, _ = fixture(root/'a')
        self.b, self.buffers, self.state = fixture(root/'b')

    def load_candidate(self):
        seal(self.b.parent/'dump', self.buffers, self.state)
        return compare.load_set(self.b)

    def result(self):
        return compare.compare(compare.load_set(self.a), self.load_candidate())

    def test_every_allocation_matches(self):
        result = self.result()
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['compared_source_keys']),5)
        self.assertEqual(result['compared_bytes'],56)

    def test_scratch_and_pinned_bytes_cannot_be_omitted(self):
        for label in ('card0:draft:scratch','card0:draft:publication','card0:draft:half-staging'):
            with self.subTest(label=label):
                original = self.buffers[label]
                self.buffers[label] = b'\x01'+original[1:]
                self.assertFalse(self.result()['passed'])
                self.buffers[label] = original

    def test_raw_payload_tamper_fails_seal(self):
        path = self.b.parent/'dump/state.bundle'
        path.write_bytes(b'x'+path.read_bytes()[1:])
        with self.assertRaisesRegex(ValueError,'bytes differ'):
            compare.load_set(self.b)

    def test_layout_required_for_every_allocation(self):
        del self.state['layouts']['card0:draft:scratch']
        with self.assertRaisesRegex(ValueError,'layout inventory'):
            self.load_candidate()

    def test_equal_extent_different_shape_fails_comparison(self):
        self.state['layouts']['card0:draft:blk.0.qsa.keys']['shape'] = [4]
        self.assertFalse(self.result()['passed'])

    def test_unknown_semantics_and_schema_refused(self):
        self.state['layouts']['card0:draft:scratch']['semantic'] = 'ignore-me'
        with self.assertRaisesRegex(ValueError,'unregistered'):
            self.load_candidate()
        self.state['schema'] = 'ownrt.draft-state.v2'
        with self.assertRaisesRegex(ValueError,'schema'):
            self.load_candidate()

    def test_pending_or_disabled_host_refused(self):
        for key, value in [('async_pending',True),('disabled',True),('reverse_hidden_present',True),
                           ('queued_probe',3),('depth_probe',1),('pending_head',True)]:
            with self.subTest(key=key):
                original = self.state['host'][key]
                self.state['host'][key] = value
                with self.assertRaisesRegex(ValueError,'quiescent'):
                    self.load_candidate()
                self.state['host'][key] = original

    def test_device_position_cannot_disagree_with_host(self):
        self.buffers['card0:draft:position'] = struct.pack('<i',2)
        with self.assertRaisesRegex(ValueError,'device position'):
            self.load_candidate()

    def test_native_unsigned_position_is_valid_but_still_compared_by_type(self):
        self.state['layouts']['card0:draft:position']['dtype'] = 'U32'
        self.load_candidate()
        self.assertFalse(self.result()['passed'])

    def test_pair_sequence_must_match_even_with_identical_state(self):
        data = json.loads(self.b.read_text())
        data['input_identity']['pair_sequence_sha256'] = 'd'*64
        self.b.write_text(json.dumps(data))
        self.assertFalse(self.result()['passed'])

    def test_pinned_transport_inventory_required(self):
        del self.buffers['card0:draft:publication']
        del self.state['layouts']['card0:draft:publication']
        with self.assertRaisesRegex(ValueError,'missing pinned'):
            self.load_candidate()


if __name__ == '__main__':
    unittest.main()
