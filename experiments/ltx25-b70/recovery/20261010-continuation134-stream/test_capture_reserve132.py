"""Packet132 reserve arithmetic and fail-closed qualification, stdlib CPU only."""
import copy
import os
import unittest
from unittest.mock import Mock, patch

import cone_memory131 as cone
from test_cone_memory131 import environment, fake, FIRST


class CaptureReserve132(unittest.TestCase):
    def test_default_and_explicit_parent(self):
        self.assertEqual(cone.reserve_mode({}), 'parent')
        self.assertEqual(cone.reserve_mode({cone.RESERVE_ENV: 'parent'}), 'parent')
        self.assertEqual(cone.reserve_bytes(), 5368709120)

    def test_scaled_mode_is_recognized_without_approving_it(self):
        self.assertEqual(cone.reserve_mode({cone.RESERVE_ENV: 'scaled-476'}), 'scaled-476')

    def test_invalid_modes_rejected(self):
        for value in ('', 'off', '4.76', 'scaled-476 ', None, 1, True, [], {}):
            for operation in (lambda: cone.reserve_mode({cone.RESERVE_ENV: value}),
                              lambda: cone.reserve_bytes(value),
                              lambda: cone.reserve_projection(value)):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    operation()

    def test_scaled_projection_rounds_up_fractional_byte(self):
        record = cone.reserve_projection('scaled-476')
        self.assertEqual(record['capture_reserve_bytes'], 5111011083)
        self.assertGreaterEqual(record['capture_reserve_bytes'] * 100, 476 * cone.GIB)
        self.assertLess((record['capture_reserve_bytes'] - 1) * 100, 476 * cone.GIB)

    def test_121_measurement_and_quadratic_estimate_are_distinct(self):
        record = cone.reserve_projection('scaled-476')
        self.assertEqual(record['measured_121_reserved_growth_bytes'], 3430940672)
        self.assertEqual(record['scaled_145_estimate_bytes'], 4838162432)
        self.assertEqual(3430940672 * 19 * 19, 4838162432 * 16 * 16)
        self.assertFalse(record['reserve_is_measured'])

    def test_scaled_margin_and_reduction_are_exact(self):
        record = cone.reserve_projection('scaled-476')
        self.assertEqual(record['estimate_margin_bytes'], 272848651)
        self.assertEqual(record['reduction_from_parent_bytes'], 257698037)

    def test_scaled_projection_retains_floor_and_screen(self):
        record = cone.reserve_projection('scaled-476')
        self.assertEqual(record['floor_bytes'], 9663676416)
        self.assertEqual(record['screening_bytes'], 805306368)
        self.assertEqual(record['first_capture_required_bytes'], 15579993867)
        self.assertEqual(15825240064 - record['first_capture_required_bytes'], 245246197)

    def test_parent_projection_retains_131_arithmetic(self):
        record = cone.reserve_projection()
        self.assertEqual(record['first_capture_required_bytes'], 15837691904)
        self.assertEqual(record['reduction_from_parent_bytes'], 0)
        self.assertEqual(record['estimate_margin_bytes'], 530546688)
        self.assertTrue(record['launch_admitted'])
        self.assertFalse(record['reserve_is_measured'])

    def test_scaled_projection_cannot_be_mistaken_for_admission(self):
        record = cone.reserve_projection('scaled-476')
        self.assertFalse(record['launch_admitted'])
        self.assertIn('not a 145 peak or upper bound', record['evidence_limitation'])
        with self.assertRaises(ValueError):
            cone.validate_record(record)

    def test_scaled_bytes_fail_closed_with_specific_missing_evidence(self):
        with self.assertRaisesRegex(ValueError, '145-frame capture peak or an upper bound'):
            cone.reserve_bytes('scaled-476')

    def test_exact_145_scope_does_not_override_missing_measurement(self):
        env = environment(); env[cone.RESERVE_ENV] = 'scaled-476'
        with self.assertRaisesRegex(ValueError, 'not qualified'):
            cone.validate_scope(env)

    def test_scaled_rejected_with_cone_off_as_well(self):
        with self.assertRaisesRegex(ValueError, 'not qualified'):
            cone.validate_scope({cone.RESERVE_ENV: 'scaled-476'})

    def test_scaled_admission_never_reads_free_or_releases_allocator(self):
        for first in (True, False):
            for mode in ('off', 'replica-release'):
                torch, _ = fake(); free = Mock(side_effect=AssertionError('must not inspect'))
                with self.subTest(first=first, mode=mode), self.assertRaisesRegex(ValueError, 'not qualified'):
                    cone.admit(torch, free, mode=mode, first_capture=first, reserve_mode='scaled-476')
                free.assert_not_called()
                torch.xpu.empty_cache.assert_not_called()

    def test_explicit_parent_admission_is_identical_to_default(self):
        torch, free = fake(FIRST)
        default = cone.admit(torch, free, mode='replica-release', first_capture=True)
        torch, free = fake(FIRST)
        explicit = cone.admit(torch, free, mode='replica-release', first_capture=True,
                              reserve_mode='parent')
        self.assertEqual(default, explicit)

    def test_explicit_parent_off_does_no_work(self):
        free = Mock(side_effect=AssertionError('must not inspect'))
        self.assertIsNone(cone.admit(None, free, mode='off', first_capture=True,
                                    reserve_mode='parent'))
        free.assert_not_called()

    def test_evidence_validator_is_independent_of_ambient_environment(self):
        torch, free = fake(FIRST)
        record = cone.admit(torch, free, mode='replica-release', first_capture=True)
        with patch.dict(os.environ, {cone.RESERVE_ENV: 'scaled-476'}):
            self.assertTrue(cone.validate_record(record, reserve_mode='parent'))
            self.assertTrue(cone.validate_record(record))
            self.assertEqual(cone.reserve_bytes(), 5368709120)

    def test_explicit_scaled_evidence_is_rejected_even_if_parent_receipt_valid(self):
        torch, free = fake(FIRST)
        record = cone.admit(torch, free, mode='replica-release', first_capture=True)
        with self.assertRaisesRegex(ValueError, 'not qualified'):
            cone.validate_record(record, reserve_mode='scaled-476')

    def test_fabricated_scaled_budget_cannot_pass_parent_validator(self):
        torch, free = fake(FIRST)
        record = cone.admit(torch, free, mode='replica-release', first_capture=True)
        changed = copy.deepcopy(record)
        changed['capture_reserve_bytes'] = cone.SCALED_RESERVE
        changed['required_bytes'] = cone.FLOOR + cone.SCREEN + cone.SCALED_RESERVE
        changed['margin_bytes'] = changed['free_bytes'] - changed['required_bytes']
        changed['allocator_release']['required_bytes'] = changed['required_bytes']
        with self.assertRaises(ValueError):
            cone.validate_record(changed)


if __name__ == '__main__':
    unittest.main()
