"""Run real V30 model/loader construction in isolated CPU-only processes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from worker_init_rehearsal import HERE, SOURCE, DEPENDENCIES

AVAILABLE = (importlib.util.find_spec('torch') is not None and
             SOURCE.is_dir() and DEPENDENCIES.is_dir())
OLD_GUARD_BLOB = 'e1940e561f559cf92b846c94380da2b270674332'
OLD_GUARD_SHA256 = 'f34291011176d86fcd1ce36908f90d26fa7422c744ace2f47cf9324a3e8e73cf'


@unittest.skipUnless(AVAILABLE, 'requires existing LTX torch, V30 clone and dependency venv')
class WorkerInitRehearsalTests(unittest.TestCase):
    def run_rank(self, rank):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'receipt.json'
            proc = subprocess.run([sys.executable, str(HERE/'worker_init_rehearsal.py'),
                                   '--rank', str(rank), '--output', str(output)],
                                  capture_output=True, text=True, timeout=90,
                                  env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            receipt = json.loads(output.read_text())
            self.assertTrue(receipt['passed'])
            self.assertEqual(receipt['rank'], rank)
            self.assertEqual(receipt['v5_parameters'], 8)
            self.assertEqual(receipt['staging']['live'], {})
            self.assertEqual(receipt['constructor_expert_map_calls'], 4)
            self.assertEqual(len(receipt['expert_maps']), 52)
            self.assertEqual(len(receipt['placement_checks']), 48)
            self.assertEqual(receipt['placement_sha256'], hashlib.sha256(
                (HERE/'placement-attempt6-v5.json').read_bytes()).hexdigest())
            for mapping in receipt['expert_maps']:
                self.assertEqual(mapping['values'],
                                 [-1]*(rank*128) + list(range(128)) + [-1]*((3-rank)*128))
                self.assertEqual(mapping['dtype'], 'torch.int32')
            self.assertEqual(receipt['pressure_replay']['pressure_bytes'], 80005660672)
            self.assertIn('expert_map_manager.py', receipt['pressure_replay']['sibling_traceback'])
            self.assertIn('first stop:', receipt['pressure_replay']['sibling_traceback'])
            if dest := os.environ.get('SCREEN1B_CPU_EVIDENCE_DIR'):
                Path(dest).mkdir(parents=True, exist_ok=True)
                (Path(dest)/f'rank{rank}.json').write_text(output.read_text())
                (Path(dest)/f'rank{rank}.log').write_text(proc.stdout + proc.stderr)

    def test_rank0(self): self.run_rank(0)
    def test_rank1(self): self.run_rank(1)
    def test_rank2(self): self.run_rank(2)
    def test_rank3(self): self.run_rank(3)

    def test_attempt2_guard_fails_real_rope_constructor(self):
        old = subprocess.run(['git', 'show', OLD_GUARD_BLOB], cwd=HERE,
                             check=True, capture_output=True).stdout
        self.assertEqual(hashlib.sha256(old).hexdigest(), OLD_GUARD_SHA256)
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp)/'attempt2_guard.py'
            original.write_bytes(old)
            proc = subprocess.run([sys.executable, str(HERE/'worker_init_rehearsal.py'),
                                   '--guard-source', str(original)],
                                  capture_output=True, text=True, timeout=90,
                                  env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('rotary_embedding/base.py', proc.stderr)
        self.assertIn('cache = cache.to(dtype)', proc.stderr)
        self.assertIn('LoadCancelled: conversion exceeds 256 MiB:', proc.stderr)
        if dest := os.environ.get('SCREEN1B_CPU_EVIDENCE_DIR'):
            Path(dest).mkdir(parents=True, exist_ok=True)
            (Path(dest)/'attempt2-guard-negative.log').write_text(proc.stdout + proc.stderr)


if __name__ == '__main__':
    unittest.main()
