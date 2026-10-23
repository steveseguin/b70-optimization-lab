"""CPU hashes and filesystem refusals only; no launch/service/native execution."""
import copy
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import bounded_serving_profile as profile


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One real baseline verification; mutation tests mock only expensive
        # repeated hashing. The public API has no fixture/admission override.
        cls.baseline_check = staticmethod(profile._baseline)
        cls.baseline = cls.baseline_check()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='profile-cpu-', dir=profile.HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output, self.states = self.root / 'output', self.root / 'checkpoints'
        self.baseline_mock = patch.object(profile, '_baseline', return_value=copy.deepcopy(self.baseline))
        self.baseline_mock.start(); self.addCleanup(self.baseline_mock.stop)
        self.disk_mock = patch.object(profile.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(100_000_000_000, 0, 40_000_000_000))
        self.disk_mock.start(); self.addCleanup(self.disk_mock.stop)

    def build(self):
        return profile.build_profile(self.output, self.states)

    def test_real_baseline_and_exact_three_deltas(self):
        row = self.build()
        profile.validate_profile(row)
        before = self.baseline[0]['native_argv']; after = row['native_argv']
        changed = [before[i-1] for i in range(len(before)) if before[i] != after[i]]
        self.assertEqual(changed, ['--output', '--request-front-max-requests', '--request-front-checkpoints'])
        self.assertEqual(row['limits']['requests'], 16)
        self.assertFalse(row['live_admission_ready'])
        self.assertFalse(row['storage_budget']['receipt_admitted'])
        self.assertFalse(self.output.exists()); self.assertFalse(self.states.exists())

    def test_mutated_admission_refused(self):
        base = self.build()
        changes = [('limits', 'context', 8192), ('limits', 'requests', 17),
                   ('limits', 'idle_seconds', 300), ('limits', 'absolute_seconds', 7200),
                   ('limits', 'parking_bytes', 0), ('limits', 'planned_write_bytes', 1),
                   ('binary', 'sha256', '0'*64), ('storage_budget', 'receipt_admitted', True),
                   ('source_sha256', next(iter(base['source_sha256'])), '0'*64)]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                row = copy.deepcopy(base); row[section][key] = value
                with self.assertRaises(profile.ProfileRefusal): profile.validate_profile(row)
        for key, value in [('live_admission_ready', True), ('device_executed', 0),
                           ('native_stop_token_ids', [248044]), ('bind_host', '0.0.0.0'), ('model', 'other')]:
            row = copy.deepcopy(base); row[key] = value
            with self.assertRaises(profile.ProfileRefusal): profile.validate_profile(row)
        row = copy.deepcopy(base); row['native_argv'] += ['--checked']
        with self.assertRaises(profile.ProfileRefusal): profile.validate_profile(row)
        row = copy.deepcopy(base); row['identity']['geometry']['context'] = 8192
        with self.assertRaises(profile.ProfileRefusal): profile.validate_profile(row)

    def test_used_symlink_nested_missing_external_paths_refused(self):
        self.output.mkdir(mode=0o700)
        with self.assertRaises(profile.ProfileRefusal): self.build()
        self.output.rmdir(); self.output.symlink_to(self.root / 'absent')
        with self.assertRaises(profile.ProfileRefusal): self.build()
        self.output.unlink()
        for out, state in [(self.output, self.output), (self.output, self.output/'nested'),
                           (self.root/'missing'/'output', self.states),
                           (Path('/tmp/profile-external'), self.states)]:
            with self.subTest(out=out, state=state):
                with self.assertRaises(profile.ProfileRefusal): profile.build_profile(out, state)

    def test_attached_requires_private_existing_directories(self):
        row = self.build()
        with self.assertRaises(profile.ProfileRefusal): profile.validate_profile(row, check_fresh=False)
        self.output.mkdir(mode=0o700); self.states.mkdir(mode=0o700)
        profile.validate_profile(row, check_fresh=False)
        self.states.chmod(0o755)
        with self.assertRaises(profile.ProfileRefusal): profile.validate_profile(row, check_fresh=False)
        self.states.chmod(0o700)
        with self.assertRaises(profile.ProfileRefusal): profile.validate_profile(row)

    def test_root_forecast_and_attached_floor(self):
        floor = profile.LIMITS['disk_floor_bytes']; reserve = profile.LIMITS['planned_write_bytes']
        with patch.object(profile.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(100_000_000_000,0,floor+reserve-1)):
            with self.assertRaises(profile.ProfileRefusal): self.build()
        row = self.build(); self.output.mkdir(mode=0o700); self.states.mkdir(mode=0o700)
        with patch.object(profile.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(100_000_000_000,0,floor-1)):
            with self.assertRaises(profile.ProfileRefusal): profile.validate_profile(row, check_fresh=False)

    def test_baseline_flags_not_silently_rewritten(self):
        ready, identity, binary = copy.deepcopy(self.baseline)
        ready['native_argv'][ready['native_argv'].index('--cache-bytes')+1] = '23049601024'
        with patch.object(profile, '_baseline', return_value=(ready, identity, binary)):
            with self.assertRaises(profile.ProfileRefusal): self.build()

    def test_loaded_codec_dependency_origin_refused(self):
        import regex
        with patch.object(regex, '__file__', '/tmp/ambient-regex/__init__.py'):
            with self.assertRaisesRegex(profile.ProfileRefusal, 'dependency origin'):
                self.baseline_check()

    def test_own_stack_and_actual_device_audit_are_bound(self):
        row = self.build()
        names = ('bounded_serving_profile.py', 'test_bounded_serving_profile.py',
                 'bounded_serving_session.py', 'test_bounded_serving_session.py',
                 'bounded_evidence.py', 'test_bounded_evidence.py',
                 'test_checkpoint_engine.py', 'session_lifecycle.py', 'test_session_lifecycle.py',
                 'receipts/bounded-serving-storage-budget.json')
        for name in names:
            relative = str((profile.HERE / name).relative_to(profile.ROOT))
            self.assertEqual(row['source_sha256'][relative], profile.sha(profile.HERE / name))
        self.assertEqual(row['device_audit_sha256'], profile.DEVICE_AUDIT_SHA256)
        self.assertEqual(row['storage_budget']['receipt_sha256'], profile.BUDGET_SHA256)
        self.assertFalse(row['storage_budget']['receipt_admitted'])

    def test_device_provenance_and_budget_source_drift_refused(self):
        real_sha = profile.sha
        for target in (profile.DEVICE_AUDIT, profile.BUDGET_RECEIPT, profile.HERE/'bounded_evidence.py'):
            with self.subTest(path=target):
                with patch.object(profile, 'sha', side_effect=lambda path: '0'*64 if Path(path) == target else real_sha(path)):
                    with self.assertRaises(profile.ProfileRefusal): self.build()

    def test_stale_new_source_pin_refused(self):
        row = self.build()
        real_sha = profile.sha
        with patch.object(profile, 'sha', side_effect=lambda path: '0'*64 if Path(path).name == 'session_lifecycle.py' else real_sha(path)):
            with self.assertRaises(profile.ProfileRefusal): profile.validate_profile(row)


if __name__ == '__main__':
    unittest.main()
