import tempfile
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
        self.assertEqual(s.BUILD_LIMIT, 8_446_804_480)

    def test_admission_preserves_other_work_and_floor(self):
        s.budget(23_000_000_000, 2_000_000_000, 2_500_000_000, 2_500_000_000)
        with self.assertRaises(RuntimeError):
            s.budget(s.FREE_FLOOR+s.CHAIN_RESERVE+99, 0, 100, 100)
        with self.assertRaises(RuntimeError):
            s.budget(100_000_000_000, s.BUILD_LIMIT, 1, 1)

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
