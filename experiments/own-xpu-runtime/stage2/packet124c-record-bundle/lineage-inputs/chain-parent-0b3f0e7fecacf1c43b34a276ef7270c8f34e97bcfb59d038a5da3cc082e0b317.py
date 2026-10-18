import unittest
from unittest.mock import patch
import storage as s


class StorageTests(unittest.TestCase):
    def test_finished_or_superseded_parents_have_no_reserve(self):
        self.assertEqual(s.parent_pending_bytes(), 0)
        self.assertEqual(s.ORACLE_GROWTH_RESERVE, 0)
        self.assertEqual(s.BUILD_BASE_BUDGET, 1_500_000_000)
        self.assertEqual(s.CPU_BUILD_LIMIT, 1_500_000_000)
        self.assertEqual(s.MODEL_CHAIN_BYTES, 5_818_804_480)

    def test_peak_cap(self):
        with patch.object(s, 'build_size', side_effect=[1_400_000_000, 0]), patch.object(s, 'admit') as admit:
            s.cpu_build_admit(99_000_000)
            admit.assert_called_once_with(99_000_000)
        with patch.object(s, 'build_size', side_effect=[1_400_000_000, 0]):
            with self.assertRaises(RuntimeError):
                s.cpu_build_admit(100_000_000)

    def test_floor_and_own_chain_remain(self):
        s.budget(19_000_000_000, 500_000_000, 2_500_000_000, 2_500_000_000)
        with self.assertRaises(RuntimeError):
            s.budget(s.FREE_FLOOR+99, 0, 100, 100)
        with self.assertRaises(RuntimeError):
            s.budget(100_000_000_000, s.BUILD_LIMIT, 1, 1)


if __name__ == '__main__':
    unittest.main()
