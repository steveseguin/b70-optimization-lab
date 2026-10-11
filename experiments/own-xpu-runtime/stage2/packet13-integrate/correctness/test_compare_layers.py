from pathlib import Path
import tempfile
import unittest
from compare_layers import compare


class Fixtures(unittest.TestCase):
    def test_pending_exact_and_divergent_are_distinct(self):
        with tempfile.TemporaryDirectory(prefix='iq3-fixture-test-') as t:
            cpu, device = Path(t)/'cpu', Path(t)/'device'
            cpu.mkdir(); device.mkdir()
            f = 'layer-00.bf16'
            (cpu/f).write_bytes(bytes(20480))
            pending = compare(cpu, device)
            self.assertFalse(pending['all_layers_match'])
            self.assertEqual(pending['compared_layers'], 0)
            (device/f).write_bytes(bytes(20480))
            self.assertFalse(compare(cpu, device)['all_layers_match'])
            self.assertTrue(compare(cpu, device, 1)['all_layers_match'])
            (device/f).write_bytes(b'\x80\x3f'+bytes(20478))
            wrong = compare(cpu, device)
            self.assertFalse(wrong['all_layers_match'])
            self.assertEqual(wrong['first_divergent_layer'], 0)
            self.assertEqual(wrong['rows'][0]['first_values'], dict(cpu=0., other=1.))
            (cpu/'layer-01.bf16').write_bytes(bytes(20480))
            (device/'layer-01.bf16').write_bytes(b'\x80\x3f'+bytes(20478))
            (device/f).unlink()
            partial = compare(cpu, device)
            self.assertEqual(partial['first_observed_divergent_layer'], 1)
            self.assertIsNone(partial['first_divergent_layer'])

    def test_empty_coverage_is_not_a_pass(self):
        with tempfile.TemporaryDirectory(prefix='iq3-empty-fixture-test-') as t:
            self.assertFalse(compare(t,t)['all_layers_match'])


if __name__ == '__main__':
    unittest.main()
