import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import storage as s

class StorageTests(unittest.TestCase):
    def test_scope_includes_final_record_pair(self):
        self.assertEqual(s.MODEL_CHAIN_BYTES, 5_818_804_480)
        self.assertEqual(sum(s.chain_window_bytes(n) for n in s.CHAIN_WINDOWS), 10_582_804_480)
        self.assertEqual(s.FREE_FLOOR, 8_000_000_000)
        self.assertEqual(s.CHAIN_RESERVE, 6_318_804_480)
        self.assertEqual(s.BUILD_LIMIT, 6_596_804_480)

    def test_admission_preserves_other_work_and_floor(self):
        with patch.object(s, 'parent_pending_bytes', return_value=s.MODEL_CHAIN_BYTES):
            s.budget(23_000_000_000, 2_000_000_000, 2_500_000_000, 2_500_000_000)
            with self.assertRaises(RuntimeError):
                s.budget(s.FREE_FLOOR+s.CHAIN_RESERVE+99, 0, 100, 100)
            with self.assertRaises(RuntimeError):
                s.budget(100_000_000_000, s.BUILD_LIMIT, 1, 1)

    def test_only_completed_bound_parent_writes_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(s.parent_pending_bytes(root), s.MODEL_CHAIN_BYTES)
            (root/'KD').mkdir()
            (root/'queue-state.json').write_text(json.dumps(dict(completed=list(s.CHAIN_WINDOWS[:6]))))
            seal=json.loads((s.P/'storage-parent-binding.json').read_text())['build_receipt_sha256']
            row=dict(window='KD',passed=True,qualifying=True,device_executed=True,card=0,context=4096,draft_rank=1,target_split=23,build_receipt_sha256=seal)
            receipt=root/'KD/window.json';receipt.write_text(json.dumps(row))
            self.assertEqual(s.parent_pending_bytes(root),s.MODEL_CHAIN_BYTES-s.chain_window_bytes('KD'))
            for key in row:
                receipt.write_text(json.dumps(dict(row,**{key:None})))
                self.assertEqual(s.parent_pending_bytes(root),s.MODEL_CHAIN_BYTES,key)
            receipt.write_text(json.dumps(row))
            (root/'queue-state.json').write_text(json.dumps(dict(completed=['KD'])))
            self.assertEqual(s.parent_pending_bytes(root),s.MODEL_CHAIN_BYTES)

    def test_stop_never_releases_parent_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'STOP').write_text('coordinator switched to packet49c\n')
            (root/'queue-state.json').write_text(json.dumps(dict(completed=list(s.CHAIN_WINDOWS[:5]))))
            self.assertEqual(s.parent_pending_bytes(root),s.MODEL_CHAIN_BYTES)

    def test_cpu_peak_and_retained_build_are_separate(self):
        self.assertEqual(s.BUILD_BASE_BUDGET,650_000_000)
        self.assertEqual(s.CPU_BUILD_LIMIT,2_500_000_000)
        with patch.object(s,'build_size',side_effect=[2_400_000_000,0]),patch.object(s,'admit') as admit:
            s.cpu_build_admit(99_000_000)
            admit.assert_called_once_with(99_000_000)
        with patch.object(s,'build_size',side_effect=[2_400_000_000,0]):
            with self.assertRaises(RuntimeError):s.cpu_build_admit(100_000_000)

    def test_early_cap_never_discards_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(s, 'build_size', return_value=1):
                self.assertEqual(s.early_retention_gate(root)['early_retained_bytes'], 5)
            with patch.object(s, 'build_size', return_value=s.EARLY_RETAINED_LIMIT):
                with self.assertRaisesRegex(RuntimeError, 'preserve evidence'):
                    s.early_retention_gate(root)

if __name__ == '__main__':
    unittest.main()
