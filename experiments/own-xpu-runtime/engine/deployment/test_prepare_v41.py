"""Tiny authenticated fixtures for the deepseek41 (v41) profile family.

No real model reads. Covers: v41 profile acceptance, placement mask 0..7
and layer<40, engram store identity, deferred draft, prepare() refusal
(binding header not yet admitted), and v41 --plan-only validation.
"""
import json
from pathlib import Path
import tempfile
import unittest

import prepare as prep


class PrepareV41Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = self.root / 'profile'; self.assets.mkdir()
        self.model = self.root / 'model'; self.model.mkdir()
        # metadata-only shard (header == whole file, no payload)
        self.meta_bytes = b'GGUFMETA'
        # payload shard: 8-byte header + 16 bytes payload (two tensors)
        self.data_bytes = b'HEADER00' + b'a' * 16
        # engram shard: header + one wide row
        self.engram_bytes = b'ENGRAM00' + b'e' * 32
        for name, blob in [('meta.gguf', self.meta_bytes), ('data.gguf', self.data_bytes),
                           ('engram.gguf', self.engram_bytes)]:
            (self.model / name).write_bytes(blob)
        # two layer-0 tensors + one layer-39 tensor; mask 6 -> owner stripe ok
        placement = (
            'data.gguf blk.0.attn_q_a.weight attention 8 8 8 0 1 2 2 4\n'
            'data.gguf blk.39.ffn_down_exps.weight routed_experts 10 8 8 39 3 3 4 2 1\n'
        ).encode()
        (self.assets / 'placement.tsv').write_bytes(placement)
        shard = lambda name, blob, hb: dict(
            name=name, bytes=len(blob), sha256=prep.digest(blob),
            header_bytes=hb, header_sha256=prep.digest(blob[:hb]),
            data_start=hb)
        self.profile = dict(
            schema='ownrt.portable-model-profile.v41', id='tiny-v41',
            architecture='deepseek41', native_context=32768, activation_dtype='F32',
            target=dict(shards=[shard('meta.gguf', self.meta_bytes, len(self.meta_bytes)),
                                shard('data.gguf', self.data_bytes, 8)],
                        placement=dict(file='placement.tsv', tensor_count=2,
                                       sha256=prep.digest(placement))),
            engram=dict(store='nvme-mmap',
                        shards=[shard('engram.gguf', self.engram_bytes, 8)],
                        tensor='per_layer_token_embd.weight',
                        rows=768022850, row_dim=256),
            draft=dict(format='gguf', admission='deferred',
                       shards=[dict(name='dspark.gguf', bytes=4, sha256=prep.digest(b'xxxx'))]),
            tokenizer=dict(source='gguf-metadata', shard='meta.gguf',
                           sha256=prep.digest(self.meta_bytes)),
            geometry=dict(dim=5120, vocab=129280, layers=40, experts=384,
                          moe_inter=2304, q_lora=1280, heads=64, head_dim=512,
                          kv_rank=512, hc_mult=4))
        self.profile_path = self.assets / 'profile.json'
        self.pin()

    def pin(self):
        self.profile_path.write_bytes(prep.encoded(self.profile))
        self.sha = prep.digest(self.profile_path.read_bytes())

    def test_v41_profile_and_placement_accepted(self):
        profile, raw, placement, rows, draft_rows, template = \
            prep.load_profile(self.profile_path, self.sha)
        self.assertEqual(profile['architecture'], 'deepseek41')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['layer'], 39)
        self.assertEqual(rows[1]['mask'], 3)  # six-owner stripe allows >3
        self.assertEqual(draft_rows, [])

    def test_v41_rejects_layer_40_and_wrong_geometry(self):
        raw = (self.assets / 'placement.tsv').read_text().replace(
            'blk.39.ffn_down_exps.weight routed_experts 10 8 8 39',
            'blk.40.ffn_down_exps.weight routed_experts 10 8 8 40')
        (self.assets / 'placement.tsv').write_text(raw)
        self.profile['target']['placement']['sha256'] = prep.digest(raw.encode())
        self.pin()
        with self.assertRaises(ValueError):
            prep.load_profile(self.profile_path, self.sha)
        self.setUp()  # restore
        self.profile['geometry']['layers'] = 41
        self.pin()
        with self.assertRaises(ValueError):
            prep.load_profile(self.profile_path, self.sha)

    def test_v41_prepare_refused_plan_only_validates(self):
        with self.assertRaises(ValueError):
            prep.prepare(self.profile_path, self.sha, self.model, self.root / 'deployment')
        result = prep.plan(self.profile_path, self.sha, self.model, self.root / 'deployment')
        kinds = [l['kind'] for l in result['locations']]
        self.assertEqual(kinds, ['target', 'engram'])
        self.assertIn('binding.json', result['artifacts'])
        self.assertNotIn('chat-template.jinja', result['artifacts'])

    def test_v41_draft_must_stay_deferred(self):
        self.profile['draft']['admission'] = 'ready'
        self.pin()
        with self.assertRaises(ValueError):
            prep.load_profile(self.profile_path, self.sha)


if __name__ == '__main__':
    unittest.main()
