#!/usr/bin/env python3
"""CPU-only controls using real historical receipt shapes; no server or device work."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('headroom100_test', HERE / 'worker-headroom-100.py')
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
RUNNER = (HERE / 'run-campaign-100.sh').read_text()
OLD = (HERE / 'run-campaign-99.sh').read_text()
ARGS = ['two-way20-28', '2', '1', '1', 'xpu:2', '256x256', '1', '120']


def write(path, data):
    path.write_text(json.dumps(data)); return {'path': str(path), 'sha256': M.sha(path.read_bytes())}


def shell(text, args=ARGS, extra=None):
    env = dict(os.environ)
    for k in ('LTX_PACKET_MANIFEST_SHA256', 'LTX_CONTROL99_BASIS', 'LTX_CONTROL99_BASIS_SHA256'):
        env.pop(k, None)
    env.update(extra or {})
    return subprocess.run(['bash', '-c', text, 'fixture', *args], env=env, capture_output=True, text=True, timeout=5)


class Headroom100(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ltx100-cpu-'); self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)
        historical = HERE.parent / 'data/place-97/two-way-w2-b1-p1-dxpu2'
        self.freeze = json.loads((historical / 'sampler-capture-freeze-f97-twowayw2b1p1dxpu2-freeze.json').read_text())
        self.summary = json.loads((historical / 'summary.json').read_text())
        self.identity = {'source_packet_manifest_sha256': M.CONTROL_MANIFEST,
            'source_packet_path': str(M.ROOT / 'prepared-encoder-upstream-99'),
            'encoder_run_dir': str(M.ROOT / 'encoder-server-upstream-99-two-way-w2-b1-p1-dxpu2-s256x256'),
            'runtime99_transition': {'control': {'layout': 'two-way', 'blocks': [23, 25], 'workers': 2,
                'batch': 1, 'shared_pool': 1, 'decode_replica': 'xpu:2', 'size': '256x256', 'references': 'w93c'}}}
        self.freeze['output_size'] = '256x256'
        self.summary['run'] = self.identity['encoder_run_dir']

    def fixture(self):
        identity = write(self.p / 'identity.json', self.identity)
        self.freeze['server_identity_sha256'] = identity['sha256']
        b = {'schema': 'ltx.rebalance100.control-basis.v1', 'packet_manifest_sha256': M.CONTROL_MANIFEST,
             'identity': identity, 'freeze': write(self.p / 'freeze.json', self.freeze),
             'summary': write(self.p / 'summary.json', self.summary)}
        x = write(self.p / 'basis.json', b)
        return Path(x['path']), x['sha256']

    def test_real_receipt_shape_projection_has_no_card0_credit(self):
        p, h = self.fixture(); d = M.validate_control_basis(p, h)
        self.assertTrue(d['admitted'])
        self.assertEqual(d['predicted_free_gib_all_workers']['xpu:0'], self.freeze['free_bytes']['xpu:0'] / M.GIB)
        self.assertAlmostEqual(d['predicted_free_gib_all_workers']['xpu:1'], self.freeze['free_bytes']['xpu:1'] / M.GIB - 3.16)
        self.assertEqual(d['card0_credit_gib'], 0)

    def test_changed_receipt_and_symlink_refuse(self):
        p, h = self.fixture(); (self.p / 'freeze.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'hash differs'): M.validate_control_basis(p, h)
        p, h = self.fixture(); target = self.p / 'other.json'; p.rename(target); p.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, 'Unsafe'): M.validate_control_basis(p, h)

    def test_coherent_wrong_control_manifest_refuses(self):
        self.identity['source_packet_manifest_sha256'] = 'b' * 64
        p, h = self.fixture()
        b = json.loads(p.read_text()); b['packet_manifest_sha256'] = 'b' * 64
        h = write(p, b)['sha256']
        with self.assertRaisesRegex(RuntimeError, 'Exact reviewed'): M.validate_control_basis(p, h)

    def test_partial_or_nonfinite_memory_refuses(self):
        for value in ({'xpu:0': 10 * M.GIB}, dict(zip(M.CARDS, [float('nan'), 10, 10, 10])),
                      dict(zip(M.CARDS, [True, 10, 10, 10]))):
            self.freeze['free_bytes'] = value
            with self.subTest(value=value), self.assertRaises((RuntimeError, ValueError)):
                M.validate_control_basis(*self.fixture())

    def test_qualification_and_chain_failures_refuse(self):
        original = copy.deepcopy((self.freeze, self.summary, self.identity))
        for kind in ('inexact', 'missing-timed', 'wrong-reference', 'wrong-blocks', 'chain-failed', 'wrong-control'):
            self.freeze, self.summary, self.identity = copy.deepcopy(original)
            timed = next(a for a in self.summary['arms'].values() if a['label'] == 'timed')
            if kind == 'inexact': timed['all_exact'] = False
            if kind == 'missing-timed': timed['clips_emitted'] = 115
            if kind == 'wrong-reference': timed['references_checked_against'] = 'batch2.json'
            if kind == 'wrong-blocks': self.freeze['chain_check']['rows'][0]['blocks'] = list(range(20))
            if kind == 'chain-failed': self.freeze['chain_check']['rows'][0]['replay_equals_eager'][0] = False
            if kind == 'wrong-control': self.identity['runtime99_transition']['control']['workers'] = 3
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                M.validate_control_basis(*self.fixture())

    def test_floor_projection_and_replica_probe_refuse(self):
        self.freeze['free_bytes']['xpu:1'] = int(5.15 * M.GIB)
        self.assertFalse(M.validate_control_basis(*self.fixture())['admitted'])
        self.freeze['free_bytes']['xpu:1'] = 10 * M.GIB
        self.freeze['free_bytes']['xpu:2'] = int(4.50 * M.GIB)
        self.assertFalse(M.validate_control_basis(*self.fixture())['admitted'])

    def test_named_layout_additive_and_live_privatepool_floor(self):
        m = M.legacy()
        self.assertEqual(m.LAYOUTS['two-way']['xpu:0'], 23)
        self.assertEqual(m.LAYOUTS['two-way']['xpu:1'], 25)
        needs = m.needed(M.LAYOUT, 1, pool=0, spec='xpu:2')
        self.assertAlmostEqual(needs['xpu:1'], 5.36)
        self.assertEqual(needs['xpu:2'], 3.8)
        free = {c: n * M.GIB for c, n in needs.items()}
        self.assertTrue(m.live(free, M.LAYOUT, 1, pool=0, spec='xpu:2')[0])
        free['xpu:1'] -= 1
        self.assertFalse(m.live(free, M.LAYOUT, 1, pool=0, spec='xpu:2')[0])
        with self.assertRaises(KeyError): m.worker_cost('unknown', 1)

    def test_actual100_identity_required_for_live_readings(self):
        identity = dict(self.identity)
        identity.update(source_packet_path=str(M.ROOT / 'prepared-encoder-rebalance-100'),
                        source_packet_manifest_sha256='a' * 64,
                        encoder_run_dir=str(M.ROOT / 'encoder-server-rebalance-100-two-way20-28-w2-b1-p1-dxpu2-s256x256'))
        ip = self.p / 'live-id.json'; ir = write(ip, identity)
        r = {'server_identity_sha256': ir['sha256'], 'output_size': '256x256', 'sampler_batch': 1,
             'sampler_workers': 2, 'sampler_shared_pool': 1, 'free_bytes': dict.fromkeys(M.CARDS, 10 * M.GIB)}
        rp = self.p / 'live.json'; write(rp, r)
        M.validate_live(rp, ip, 'a' * 64)
        with self.assertRaises(RuntimeError): M.validate_live(rp, ip, 'b' * 64)
        r['server_identity_sha256'] = 'f' * 64; write(rp, r)
        with self.assertRaises(RuntimeError): M.validate_live(rp, ip, 'a' * 64)

    def test_cpu_cli_plan_and_missing_basis_refusal(self):
        p, h = self.fixture()
        cmd = ['python3', '-B', str(HERE / 'worker-headroom-100.py'), 'plan', M.LAYOUT, '2', '1', '1', '--manifest', 'b' * 64]
        bad = subprocess.run(cmd, capture_output=True, timeout=5)
        self.assertEqual(bad.returncode, 18)
        good = subprocess.run(cmd + ['--control-basis', str(p), '--control-basis-sha256', h], capture_output=True, timeout=5)
        self.assertEqual(good.returncode, 0, good.stdout)


class Runner100(unittest.TestCase):
    def test_shell_syntax_and_narrow_pre_io_arguments(self):
        self.assertEqual(subprocess.run(['bash', '-n', str(HERE / 'run-campaign-100.sh')], timeout=5).returncode, 0)
        prefix = RUNNER[:RUNNER.index('\nR=/mnt/')]
        self.assertEqual(shell(prefix).returncode, 0)
        for i, bad in [(0, 'two-way'), (1, '3'), (2, '2'), (3, '0'), (4, 'xpu:1'), (5, '512x320'), (6, '6'), (7, '121')]:
            a = list(ARGS); a[i] = bad
            self.assertEqual(shell(prefix, a).returncode, 8)

    def test_all_actual_indices_disjoint_from99_and_each_other(self):
        prefix = RUNNER[:RUNNER.index('\nR=/mnt/')]; seen = set()
        for repeat in range(1, 6):
            a = list(ARGS); a[6] = str(repeat)
            r = shell(prefix + '\nprintf "%s %s %s %s %s %s\\n" "$CAP_BASE" "$SELF_BASE" "$SELF_N" "$PROBE_BASE" "$PROBE_N" "$TIMED_BASE"', a)
            cap, sb, sn, pb, pn, tb = map(int, r.stdout.split())
            indices = {cap, cap + 10} | set(range(sb, sb + sn)) | set(range(pb, pb + pn)) | set(range(tb, tb + 120))
            self.assertEqual(len(indices), 141); self.assertFalse(indices & seen)
            self.assertGreaterEqual(min(indices), 97000000); self.assertLess(max(indices), 100000000)
            self.assertEqual(tb, 98000000 + 10000 * (repeat - 1)); seen |= indices

    def test_missing_digest_or_basis_refuses_without_writes(self):
        part = RUNNER[:RUNNER.index('\nstep()')]
        with tempfile.TemporaryDirectory(prefix='ltx100-runner-test-') as td:
            part = part.replace('BASE_OUT=$LANE/data/rebalance-100', 'BASE_OUT=' + td + '/campaigns')
            for env in ({}, {'LTX_PACKET_MANIFEST_SHA256': 'a' * 64},
                        {'LTX_PACKET_MANIFEST_SHA256': 'bad', 'LTX_CONTROL99_BASIS': '/tmp/basis', 'LTX_CONTROL99_BASIS_SHA256': 'b' * 64}):
                self.assertEqual(shell(part, extra=env).returncode, 8)
                self.assertFalse((Path(td) / 'campaigns').exists())

    def test_quality_lifecycle_functions_and_stages_identical(self):
        def function(text, name):
            return re.search(r'^' + name + r'\(\).*?^}\n', text, re.M | re.S).group()
        for name in ('arm', 'pid_is_server', 'queue_empty', 'missing_markers', 'failed_jobs', 'pipeline_idle_once',
                     'pipeline_idle_stable', 'stop_when_proven', 'decode_placement_check', 'summarize', 'finish', 'on_signal', 'on_exit'):
            self.assertEqual(function(RUNNER, name).replace('f100-', 'f99-'), function(OLD, name))
        stages = ['# ---- 1.', '# ---- 2.', '# ---- 3.', '# ---- 4.', '# ---- 5.', '# ---- 6.', '# ---- B=1, 7.', '# ---- B=1, 8.']
        pos = [RUNNER.index(x) for x in stages]; self.assertEqual(pos, sorted(pos))
        self.assertIn('--control-basis "$CONTROL_BASIS" --control-basis-sha256 "$CONTROL_BASIS_SHA"', RUNNER)
        self.assertEqual(RUNNER.count('--server-identity "$RUN/server-identity.json"'), 2)
        self.assertIn('arm f100-$TAG-timed $TIMED_ARM $TIMED_N $TIMED_BASE auto watch "$W93C" cycle', RUNNER)


if __name__ == '__main__':
    unittest.main(verbosity=2)
