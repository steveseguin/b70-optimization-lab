"""Packet131 fake allocator/scope gates; imports no torch or device runtime."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import cone_memory131 as cone

GIB = 2 ** 30
FIRST = 59 * GIB // 4
LATER = 39 * GIB // 4


def fake(free=14 * GIB, gain=GIB, reservation_gain=None, release_error=None):
    """Same fake callback structure as test_allocator_release130; actual free is independent of reservations."""
    state = {'calls': 0}
    def empty():
        state['calls'] += 1
        if release_error:
            raise release_error
    reserved_gain = gain if reservation_gain is None else reservation_gain
    xpu = SimpleNamespace(
        empty_cache=Mock(side_effect=empty),
        mem_get_info=Mock(side_effect=lambda card: (free + gain * bool(state['calls']), 32 * GIB)),
        memory_allocated=Mock(return_value=8 * GIB),
        memory_reserved=Mock(side_effect=lambda card: 16 * GIB - reserved_gain * bool(state['calls'])),
        max_memory_allocated=Mock(return_value=12 * GIB))
    return SimpleNamespace(xpu=xpu), Mock(side_effect=lambda: xpu.mem_get_info('xpu:3')[0])


def environment():
    return dict(cone.SCOPE, **{cone.ENV: 'replica-release'})


class ConeScope(unittest.TestCase):
    def test_default_off_preserves_parent_without_scope(self):
        self.assertEqual(cone.launch_mode({}), 'off')
        self.assertEqual(cone.validate_scope({}), 'off')

    def test_explicit_off_does_not_narrow_parent_forms(self):
        self.assertEqual(cone.validate_scope({cone.ENV: 'off', 'LTX_STREAM_FRAMES': '169',
                                             'LTX_DECODER_GRAPH_POOL_CAP_GB': '3.0'}), 'off')

    def test_invalid_modes(self):
        for value in ('', 'on', 'replica-release ', True, None, 1, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cone.launch_mode({cone.ENV: value})

    def test_exact_scope_admitted(self):
        self.assertEqual(cone.validate_scope(environment()), 'replica-release')

    def test_each_changed_scope_field_refused(self):
        for field in cone.SCOPE:
            for value in ('wrong', None, True, 1):
                env = environment(); env[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    cone.validate_scope(env)

    def test_each_missing_required_field_refused(self):
        for field in set(cone.SCOPE) - set(cone.DEFAULTS):
            env = environment(); del env[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                cone.validate_scope(env)

    def test_declared_defaults_are_the_only_omissions_allowed(self):
        env = environment()
        for field, default in cone.DEFAULTS.items():
            self.assertEqual(cone.SCOPE[field], default)
            del env[field]
        self.assertEqual(cone.validate_scope(env), 'replica-release')

    def test_any_pool_cap_is_refused(self):
        for value in ('0', '5', '', 0, True, [], {}):
            env = environment(); env['LTX_DECODER_GRAPH_POOL_CAP_GB'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'pool cap'):
                cone.validate_scope(env)


class ConeAdmission(unittest.TestCase):
    def admission(self, torch, free, first=True, mode='replica-release'):
        return cone.admit(torch, free, mode=mode, first_capture=first)

    def test_off_calls_neither_free_nor_allocator(self):
        free = Mock(side_effect=AssertionError('off must not inspect'))
        self.assertIsNone(self.admission(None, free, mode='off'))
        free.assert_not_called()

    def test_first_capture_exact_14_75_gib_boundary(self):
        torch, free = fake(FIRST)
        record = self.admission(torch, free)
        self.assertEqual(record['required_bytes'], FIRST)
        self.assertEqual(record['capture_reserve_bytes'], 5 * GIB)
        self.assertEqual(record['floor_bytes'], 9 * GIB)
        self.assertEqual(record['screening_bytes'], 3 * GIB // 4)
        self.assertEqual(record['margin_bytes'], 0)
        torch.xpu.empty_cache.assert_not_called(); free.assert_called_once_with()
        self.assertTrue(cone.validate_record(record))

    def test_later_exact_9_75_gib_boundary(self):
        torch, free = fake(LATER)
        record = self.admission(torch, free, first=False)
        self.assertEqual(record['required_bytes'], LATER)
        self.assertEqual(record['capture_reserve_bytes'], 0)
        self.assertEqual(record['margin_bytes'], 0)
        torch.xpu.empty_cache.assert_not_called()
        self.assertTrue(cone.validate_record(record))

    def test_first_capture_cannot_use_later_budget(self):
        torch, free = fake(LATER, gain=0)
        with self.assertRaises(RuntimeError) as result:
            self.admission(torch, free)
        self.assertEqual(result.exception.admission['required_bytes'], FIRST)
        self.assertEqual(result.exception.admission['margin_bytes'], -5 * GIB)
        torch.xpu.empty_cache.assert_called_once_with()

    def test_one_byte_below_both_budgets_refuses_after_one_release(self):
        for first, required in ((True, FIRST), (False, LATER)):
            torch, free = fake(required - 1, gain=0)
            with self.subTest(first=first), self.assertRaises(RuntimeError) as result:
                self.admission(torch, free, first=first)
            self.assertEqual(result.exception.admission['margin_bytes'], -1)
            torch.xpu.empty_cache.assert_called_once_with()
            self.assertEqual(free.call_count, 2)

    def test_one_release_reaches_exact_boundary_using_fresh_free(self):
        torch, free = fake(FIRST - GIB, gain=GIB)
        record = self.admission(torch, free)
        self.assertEqual(record['free_bytes'], FIRST)
        self.assertEqual(record['margin_bytes'], 0)
        self.assertEqual(record['allocator_release']['physical_free_delta_bytes'], GIB)
        self.assertEqual(set(record['allocator_release']['before']), {'xpu:%d' % i for i in range(4)})
        self.assertEqual(record['allocator_release']['scope'], 'process-wide XPU allocator')
        self.assertFalse(record['reserve_is_measured'])
        torch.xpu.empty_cache.assert_called_once_with()
        self.assertEqual(free.call_count, 2)
        self.assertTrue(cone.validate_record(record))

    def test_partial_release_is_not_retried(self):
        torch, free = fake(FIRST - GIB, gain=GIB // 2)
        with self.assertRaisesRegex(RuntimeError, 'physical free') as result:
            self.admission(torch, free)
        self.assertEqual(result.exception.admission['margin_bytes'], -GIB // 2)
        torch.xpu.empty_cache.assert_called_once_with()
        self.assertEqual(free.call_count, 2)

    def test_reserved_unused_is_not_physical_credit(self):
        torch, free = fake(FIRST - 1, gain=0, reservation_gain=5 * GIB)
        with self.assertRaises(RuntimeError) as result:
            self.admission(torch, free)
        record = result.exception.admission
        self.assertEqual(record['free_bytes'], FIRST - 1)
        self.assertEqual(record['allocator_release']['reserved_released_bytes_by_card']['xpu:3'], 5 * GIB)
        self.assertEqual(record['allocator_release']['physical_free_delta_bytes'], 0)
        torch.xpu.empty_cache.assert_called_once_with()

    def test_negative_physical_delta_stays_visible(self):
        torch, free = fake(FIRST - 1, gain=-GIB)
        with self.assertRaises(RuntimeError) as result:
            self.admission(torch, free)
        self.assertEqual(result.exception.admission['allocator_release']['physical_free_delta_bytes'], -GIB)
        torch.xpu.empty_cache.assert_called_once_with()

    def test_release_error_propagates_without_retry(self):
        torch, free = fake(release_error=RuntimeError('allocator failed'))
        with self.assertRaisesRegex(RuntimeError, 'allocator failed'):
            self.admission(torch, free)
        torch.xpu.empty_cache.assert_called_once_with(); free.assert_called_once_with()

    def test_bad_initial_free_never_releases(self):
        for value in (-1, True, 1.0, None, '15000000000'):
            torch, _ = fake()
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.admission(torch, Mock(return_value=value))
            torch.xpu.empty_cache.assert_not_called()

    def test_bad_post_release_free_never_retries(self):
        for value in (-1, True, 1.0, None):
            torch, _ = fake()
            free = Mock(side_effect=[FIRST - 1, value])
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.admission(torch, free)
            torch.xpu.empty_cache.assert_called_once_with()
            self.assertEqual(free.call_count, 2)

    def test_bad_counter_refuses_before_release(self):
        torch, free = fake(); torch.xpu.memory_reserved.return_value = 1
        torch.xpu.memory_reserved.side_effect = None
        with self.assertRaisesRegex(RuntimeError, 'census'):
            self.admission(torch, free)
        torch.xpu.empty_cache.assert_not_called()

    def test_mode_and_capture_flag_types(self):
        for mode, first in [('bad', True), (True, True), (None, True), ('off', 1),
                            ('replica-release', 0), ('replica-release', 'true'), ('off', None)]:
            free = Mock()
            with self.subTest(mode=mode, first=first), self.assertRaises(ValueError):
                self.admission(None, free, mode=mode, first=first)
            free.assert_not_called()


class ConeEvidence(unittest.TestCase):
    def record(self, release=False):
        torch, free = fake(FIRST - GIB if release else FIRST, gain=GIB)
        return cone.admit(torch, free, mode='replica-release', first_capture=True)

    def test_record_requires_mapping_schema_mode(self):
        for value in (None, [], True, {}, {'schema': 'wrong'}, {'schema': 'ltx.stream131.cone-memory.v1', 'mode': 'off'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cone.validate_record(value)

    def test_capture_phase_must_be_boolean(self):
        for value in (0, 1, None, 'true'):
            record = self.record(); record['first_capture'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_budget_terms_cannot_be_lowered_or_retyped(self):
        original = self.record()
        for key in ('capture_reserve_bytes', 'floor_bytes', 'screening_bytes', 'required_bytes'):
            for value in (original[key] - 1, float(original[key]), True, None):
                record = copy.deepcopy(original); record[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    cone.validate_record(record)

    def test_free_and_margin_must_match_physical_boundary(self):
        for field, value in [('free_bytes', FIRST - 1), ('free_bytes', float(FIRST)),
                             ('free_bytes', True), ('margin_bytes', 1), ('margin_bytes', 0.0),
                             ('margin_bytes', False)]:
            record = self.record(); record[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_release_binding_and_delta_cannot_change(self):
        original = self.record(release=True)
        changes = [('required_bytes', FIRST - 1), ('phase', 'before-decode'),
                   ('admission_free_after_bytes', FIRST + 1), ('admission_free_before_bytes', -1),
                   ('release_called', 1), ('physical_free_delta_bytes', 0),
                   ('before', {}), ('after', {})]
        for field, value in changes:
            record = copy.deepcopy(original); record['allocator_release'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_no_release_cannot_fabricate_extra_physical_free(self):
        record = self.record(); record['allocator_release']['admission_free_before_bytes'] -= 1
        with self.assertRaises(ValueError):
            cone.validate_record(record)

    def test_reserve_is_always_labeled_unmeasured(self):
        for value in (True, 0, None, 'false'):
            record = self.record(); record['reserve_is_measured'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_nested_allocator_record_requires_mapping(self):
        for value in (None, [], True, 'record'):
            record = self.record(); record['allocator_release'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_nested_allocator_identity_is_bound(self):
        for field, value in [('schema', 'wrong'), ('mode', 'off'), ('scope', 'xpu:3 only'),
                             ('reclaim_is_not_guaranteed', False)]:
            record = self.record(release=True); record['allocator_release'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_release_census_must_cover_four_cards(self):
        record = self.record(release=True); del record['allocator_release']['after']['xpu:2']
        with self.assertRaises(ValueError):
            cone.validate_record(record)

    def test_release_census_cannot_claim_unused_bytes_as_physical_free(self):
        record = self.record(release=True)
        record['allocator_release']['after']['xpu:3']['reserved_unused_upper_bound_bytes'] += GIB
        with self.assertRaises(ValueError):
            cone.validate_record(record)

    def test_counter_types_and_invariants_refuse_tampering(self):
        original = self.record(release=True)
        for field, value in [('free_bytes', True), ('total_bytes', 1), ('allocated_bytes', 0.0),
                             ('reserved_bytes', 1), ('peak_allocated_bytes', 1),
                             ('reserved_unused_upper_bound_bytes', -1)]:
            record = copy.deepcopy(original)
            record['allocator_release']['after']['xpu:0'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_counter_total_and_peak_cannot_change_illegally(self):
        original = self.record(release=True)
        for field, value in [('total_bytes', 33 * GIB), ('peak_allocated_bytes', 11 * GIB)]:
            record = copy.deepcopy(original)
            record['allocator_release']['after']['xpu:1'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_reservation_deltas_require_exact_four_card_integer_values(self):
        original = self.record(release=True)
        for value in ({}, None, {'xpu:3': GIB}, dict.fromkeys(('xpu:%d' % i for i in range(4)), float(GIB)),
                      dict.fromkeys(('xpu:%d' % i for i in range(4)), GIB + 1)):
            record = copy.deepcopy(original)
            record['allocator_release']['reserved_released_bytes_by_card'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_duration_must_be_finite_nonnegative_real(self):
        for value in (-1, float('nan'), float('inf'), True, '0', None):
            record = self.record(release=True); record['allocator_release']['seconds'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_no_release_cannot_carry_fake_release_counters(self):
        for field, value in [('before', {}), ('after', {}), ('physical_free_delta_bytes', 0),
                             ('reserved_released_bytes_by_card', {}), ('seconds', 0)]:
            record = self.record(); record['allocator_release'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                cone.validate_record(record)

    def test_nested_audit_budget_types_do_not_accept_float_alias(self):
        for field in ('required_bytes', 'admission_free_after_bytes', 'admission_free_before_bytes',
                      'physical_free_delta_bytes'):
            record = self.record(release=True)
            record['allocator_release'][field] = float(record['allocator_release'][field])
            with self.subTest(field=field), self.assertRaises(ValueError):
                cone.validate_record(record)


if __name__ == '__main__':
    unittest.main()
