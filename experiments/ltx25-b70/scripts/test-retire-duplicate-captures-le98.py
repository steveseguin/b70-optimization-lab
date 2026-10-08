#!/usr/bin/env python3
"""CPU tests for retire-duplicate-captures-le98.py on a synthetic tree (no real captures)."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SCRATCH = Path(os.environ.get('LE98_TEST_TMP', tempfile.gettempdir()))


def load():
    spec = importlib.util.spec_from_file_location('le98', HERE / 'retire-duplicate-captures-le98.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def safetensors(payloads, meta=None):
    header, blob, off = {}, b'', 0
    for k in ('audio_latent', 'images', 'video_latent', 'waveform'):
        d = payloads[k]
        header[k] = {'dtype': 'F32', 'shape': [len(d) // 4], 'data_offsets': [off, off + len(d)]}
        blob += d; off += len(d)
    if meta:
        header['__metadata__'] = meta
    h = json.dumps(header).encode()
    return len(h).to_bytes(8, 'little') + h + blob


def fixture(tag):
    return {k: (tag + k).encode() * 16 for k in ('audio_latent', 'images', 'video_latent', 'waveform')}


class Tree:
    def __init__(self, m):
        self.m = m
        self.base = Path(tempfile.mkdtemp(prefix='le98-test-', dir=SCRATCH))
        self.root = self.base / 'root'; self.repo = self.base / 'repo'; self.data = self.repo / 'data'
        (self.root / 'output/validation').mkdir(parents=True); self.data.mkdir(parents=True)
        (self.data / 'resume').mkdir()
        (self.repo / 'CURRENT.md').write_text('nothing here\n')
        m.ROOT = self.root; m.DATA = self.data; m.RECEIPT_DIRS = [self.data / 'resume']
        m.CURRENT = self.repo / 'CURRENT.md'; m.WORKERS = 1; m.CUTOFF_NS = 2**62
        m.git_tracked = lambda: [p for p in self.data.rglob('*') if p.is_file()]

    def capture(self, name, tag, meta=None, parity=True):
        d = self.root / 'output/validation' / name; d.mkdir()
        p = fixture(tag)
        (d / 'tensors.safetensors').write_bytes(safetensors(p, meta))
        (d / 'summary.json').write_text(json.dumps({'run_name': name, 'tensors': {
            k: {'dtype': 'torch.float32', 'shape': [len(v) // 4], 'sha256': hashlib.sha256(v).hexdigest()}
            for k, v in p.items()}}))
        if parity:
            (self.data / (name + '-parity.json')).write_text(json.dumps(
                {'status': 'passed', 'executions': [{'name': 'ref'}, {'name': name}]}))
        return d / 'tensors.safetensors'

    def throughput(self, family, all_exact=True):
        (self.data / (family + '-throughput.json')).write_text(json.dumps({'prefix': family, 'all_exact': all_exact}))


class Le98(unittest.TestCase):
    def setUp(self):
        self.m = load(); self.t = Tree(self.m)
        t = self.t
        t.capture('f96-arm-ref-00', 'A', parity=False)            # protected reference keeper
        t.throughput('f96-arm-timed')
        self.paths = [t.capture(f'f96-arm-timed-{i:02d}', 'AB'[i % 2]) for i in range(6)]

    def tearDown(self):
        shutil.rmtree(self.t.base)

    def plan(self, packet=96):
        out = self.t.repo / f'plan-{packet}.json'
        self.m.exclusive_json(out, self.m.build_plan(packet))
        return out, self.m.fp(out)['sha256']

    def test_roundtrip_apply_and_restore(self):
        out, sha = self.plan()
        plan = json.loads(out.read_text())
        names = sorted(r['name'] for r in plan['retire'])
        self.assertEqual(names, [f'f96-arm-timed-{i:02d}' for i in (2, 3, 4, 5)])
        kinds = {r['name']: (r['keeper_kind'], Path(r['retained']['path']).parent.name) for r in plan['retire']}
        self.assertEqual(kinds['f96-arm-timed-02'], ('protected-reference', 'f96-arm-ref-00'))
        self.assertEqual(kinds['f96-arm-timed-03'], ('family-first', 'f96-arm-timed-01'))
        before = {p: p.read_bytes() for p in self.paths}
        self.m.operate('apply', out, sha, self.t.repo / 'receipt.json')
        rec = json.loads((self.t.repo / 'receipt.json').read_text())
        self.assertEqual(rec['status'], 'completed'); self.assertEqual(rec['completed_count'], 4)
        for i, p in enumerate(self.paths):
            self.assertEqual(p.exists(), i < 2)
            self.assertTrue((p.parent / 'summary.json').exists())
        self.assertTrue((self.t.root / 'output/validation/f96-arm-ref-00/tensors.safetensors').exists())
        events = (self.t.repo / 'receipt.json.events.jsonl').read_text().splitlines()
        self.assertEqual(len(events), 8)
        # restore needs 50 GiB headroom; bypass admission only for the synthetic copy test
        self.m.FLOOR = 0
        self.m.operate('restore', out, sha, self.t.repo / 'restore.json')
        for p in self.paths:
            self.assertEqual(p.read_bytes(), before[p])
        with self.assertRaises(RuntimeError):     # no overwrite on a second restore
            self.m.operate('restore', out, sha, self.t.repo / 'restore2.json')

    def test_skips(self):
        t = self.t
        t.capture('f96-arm-timed-06', 'A', parity=False)               # no parity
        t.capture('f96-arm-timed-07', 'A', meta={'x': 'y'})            # same tensors, different file
        t.throughput('f96-bad-timed', all_exact=False)
        t.capture('f96-bad-timed-00', 'A'); t.capture('f96-bad-timed-01', 'A')
        t.capture('f96-arm-proofs-00', 'A'); t.capture('f96-arm-proofs-01', 'A')
        t.capture('f99-new-timed-00', 'A'); t.throughput('f99-new-timed'); t.capture('f99-new-timed-01', 'A')
        t.capture('f96-noth-timed-00', 'A'); t.capture('f96-noth-timed-01', 'A')
        held = open(self.paths[5], 'rb')
        try:
            out, _ = self.plan()
        finally:
            held.close()
        plan = json.loads(out.read_text())
        names = sorted(r['name'] for r in plan['retire'])
        self.assertEqual(names, ['f96-arm-timed-02', 'f96-arm-timed-03', 'f96-arm-timed-04'])
        reasons = {Path(s.get('path', '')).parent.name or s['family']: s['reason'] for s in plan['skipped']}
        self.assertIn('parity', reasons['f96-arm-timed-06'])
        self.assertIn('whole-file', reasons['f96-arm-timed-07'])
        self.assertIn('open', reasons['f96-arm-timed-05'])
        self.assertIn('all_exact', reasons['f96-bad-timed'])
        self.assertIn('throughput', reasons['f96-noth-timed'])
        self.assertEqual(plan['out_of_scope_arm_captures'], {'f96-arm-proofs': 2})
        self.assertEqual(self.m.census(99)['rows'], [])                # packet >= 99 never selected

    def test_today_and_current_exclusions(self):
        self.m.CUTOFF_NS = 0
        self.assertEqual(self.m.build_plan(96)['retire'], [])
        self.m.CUTOFF_NS = 2**62
        self.t.repo.joinpath('CURRENT.md').write_text('evidence f96-arm-timed-04 here')
        names = [r['name'] for r in self.m.build_plan(96)['retire']]
        self.assertNotIn('f96-arm-timed-04', names)

    def test_tamper_after_plan_refuses_before_intent(self):
        out, sha = self.plan()
        os.utime(self.paths[3], ns=(1, 1))
        with self.assertRaises(RuntimeError):
            self.m.operate('apply', out, sha, self.t.repo / 'receipt.json')
        self.assertFalse((self.t.repo / 'receipt.json.intent.json').exists())
        self.assertTrue(all(p.exists() for p in self.paths))

    def test_keeper_change_refuses(self):
        out, sha = self.plan()
        k = self.t.root / 'output/validation/f96-arm-ref-00/tensors.safetensors'
        os.utime(k, ns=(5, 5))
        with self.assertRaises(RuntimeError):
            self.m.operate('apply', out, sha, self.t.repo / 'receipt.json')
        self.assertTrue(all(p.exists() for p in self.paths))

    def test_receipt_hash_mismatch_refuses_plan(self):
        k = str(self.t.root / 'output/validation/f96-arm-timed-01/tensors.safetensors')
        (self.t.data / 'resume/old-plan.json').write_text(json.dumps({'keep': [{'path': k, 'sha256': '0' * 64}]}))
        with self.assertRaises(RuntimeError):
            self.m.build_plan(96)

    def test_receipt_named_capture_is_protected(self):
        k = str(self.paths[4])
        (self.t.data / 'resume/old-plan.json').write_text(json.dumps({'protected': [k]}))
        names = [r['name'] for r in self.m.build_plan(96)['retire']]
        self.assertNotIn('f96-arm-timed-04', names)

    def test_own_plan_in_receipt_dir_does_not_self_protect(self):
        out = self.t.data / 'resume/retirement-96-x.plan.json'
        self.m.exclusive_json(out, self.m.build_plan(96))
        sha = self.m.fp(out)['sha256']
        self.m.operate('apply', out, sha, self.t.data / 'resume/retirement-96-x.json')
        self.assertEqual([p.exists() for p in self.paths], [True, True, False, False, False, False])

    def test_plan_sha_and_existing_receipt(self):
        out, sha = self.plan()
        with self.assertRaises(RuntimeError):
            self.m.operate('apply', out, '0' * 64, self.t.repo / 'r.json')
        (self.t.repo / 'r.json').write_text('{}')
        with self.assertRaises(RuntimeError):
            self.m.operate('apply', out, sha, self.t.repo / 'r.json')
        self.assertTrue(all(p.exists() for p in self.paths))

    def test_new_candidate_after_plan_is_not_deleted(self):
        out, sha = self.plan()
        extra = self.t.capture('f96-arm-timed-06', 'A')
        self.m.operate('apply', out, sha, self.t.repo / 'receipt.json')
        self.assertTrue(extra.exists())


if __name__ == '__main__':
    unittest.main()
