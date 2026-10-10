"""Pure CPU adversarial validation of allocator admission receipts."""
import copy
import unittest

import allocator_release130 as release

GIB = 2 ** 30


def valid_residency(called=False):
    resident, transient = 834267746, 13 * GIB // 2

    def budget(phase, weight):
        required = weight + transient + 2 * GIB + 3 * GIB // 4
        free = required + GIB // 4
        audit = dict(schema='ltx.stream130.allocator-release.v1', mode='before-admission', phase=phase,
                     required_bytes=required, admission_free_before_bytes=free,
                     admission_free_after_bytes=free, release_called=False,
                     scope='process-wide XPU allocator', reclaim_is_not_guaranteed=True)
        return dict(free_bytes=free, new_resident_bytes=weight, transient_budget_bytes=transient,
                    floor_bytes=2 * GIB, margin_bytes=GIB, allocator_release=audit)

    result = dict(device='xpu:2', resident_bytes=resident, transient_budget_bytes=transient, floor_bytes=2 * GIB,
                  before_install=budget('before-install', resident), after_install=budget('after-install', 0),
                  last_decode=dict(before=budget('before-decode', 0), after_free_bytes=3 * GIB))
    if called:
        audit = result['last_decode']['before']['allocator_release']
        audit.update(release_called=True, admission_free_before_bytes=8 * GIB,
                     physical_free_delta_bytes=audit['admission_free_after_bytes'] - 8 * GIB, seconds=0.02)
        pre = {f'xpu:{i}': dict(free_bytes=8 * GIB, total_bytes=32 * GIB,
                allocated_bytes=18 * GIB, reserved_bytes=22 * GIB, peak_allocated_bytes=23 * GIB,
                reserved_unused_upper_bound_bytes=4 * GIB) for i in range(4)}
        post = copy.deepcopy(pre)
        for row in post.values():
            row.update(free_bytes=10 * GIB, reserved_bytes=20 * GIB, reserved_unused_upper_bound_bytes=2 * GIB)
        audit.update(before=pre, after=post, reserved_released_bytes_by_card={f'xpu:{i}': 2 * GIB for i in range(4)})
    return result


class AllocatorEvidence(unittest.TestCase):
    def test_no_release_sufficient_is_valid(self):
        self.assertTrue(release.validate_residency(valid_residency()))

    def test_release_with_fresh_physical_free_is_valid(self):
        self.assertTrue(release.validate_residency(valid_residency(True)))

    def test_each_admission_requires_evidence(self):
        for key in ('before_install', 'after_install', 'decode'):
            row = valid_residency()
            target = row['last_decode']['before'] if key == 'decode' else row[key]
            del target['allocator_release']
            with self.subTest(key=key), self.assertRaises(ValueError): release.validate_residency(row)

    def test_wrong_mode_phase_and_threshold(self):
        for field, value in [('mode', 'off'), ('phase', 'after-install'), ('required_bytes', 17 * GIB // 2)]:
            row = valid_residency(); row['last_decode']['before']['allocator_release'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): release.validate_residency(row)

    def test_install_must_charge_new_weights(self):
        row = valid_residency(); row['before_install']['allocator_release']['required_bytes'] -= row['resident_bytes']
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_reduced_transient_refuses(self):
        row = valid_residency(); row['transient_budget_bytes'] = 6 * GIB
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_screening_cannot_be_replaced_by_base_floor(self):
        row = valid_residency(); budget = row['last_decode']['before']
        budget.update(free_bytes=17 * GIB // 2, margin_bytes=0)
        budget['allocator_release'].update(admission_free_before_bytes=17 * GIB // 2,
                                          admission_free_after_bytes=17 * GIB // 2)
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_forged_margin_refuses(self):
        row = valid_residency(); row['last_decode']['before']['margin_bytes'] += 1
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_postdecode_screen_is_required(self):
        row = valid_residency(); row['last_decode']['after_free_bytes'] = 2 * GIB
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_no_release_cannot_gain_free(self):
        row = valid_residency(); row['last_decode']['before']['allocator_release']['admission_free_before_bytes'] = 8 * GIB
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_no_release_cannot_fabricate_counter_event(self):
        row = valid_residency(); row['last_decode']['before']['allocator_release']['seconds'] = 0
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_release_requires_all_card_snapshots(self):
        row = valid_residency(True); del row['last_decode']['before']['allocator_release']['after']['xpu:3']
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_bad_census_and_bad_net_deltas_refuse(self):
        for field in ('physical_free_delta_bytes', 'reservation_delta', 'unused_bytes', 'peak'):
            row = valid_residency(True); audit = row['last_decode']['before']['allocator_release']
            if field == 'physical_free_delta_bytes': audit[field] += 1
            if field == 'reservation_delta': audit['reserved_released_bytes_by_card']['xpu:2'] += 1
            if field == 'unused_bytes': audit['after']['xpu:2']['reserved_unused_upper_bound_bytes'] += 1
            if field == 'peak': audit['after']['xpu:2']['peak_allocated_bytes'] = 22 * GIB
            with self.subTest(field=field), self.assertRaises(ValueError): release.validate_residency(row)

    def test_reservation_release_is_not_physical_credit(self):
        row = valid_residency(True); audit = row['last_decode']['before']['allocator_release']
        audit['admission_free_after_bytes'] = 8 * GIB; audit['physical_free_delta_bytes'] = 0
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_snapshots_need_not_equal_separate_admission_read(self):
        row = valid_residency(True)
        row['last_decode']['before']['allocator_release']['after']['xpu:2']['free_bytes'] = 7 * GIB
        self.assertTrue(release.validate_residency(row))

    def test_signed_reservation_delta_is_not_clamped(self):
        row = valid_residency(True); audit = row['last_decode']['before']['allocator_release']
        audit['after']['xpu:1'].update(reserved_bytes=23 * GIB, reserved_unused_upper_bound_bytes=5 * GIB)
        audit['reserved_released_bytes_by_card']['xpu:1'] = -GIB
        self.assertTrue(release.validate_residency(row))

    def test_nonfinite_and_boolean_duration_refuse(self):
        for value in (float('nan'), float('inf'), -1, True):
            row = valid_residency(True); row['last_decode']['before']['allocator_release']['seconds'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): release.validate_residency(row)

    def test_boolean_count_is_not_an_integer(self):
        row = valid_residency(True); row['last_decode']['before']['allocator_release']['after']['xpu:0']['free_bytes'] = True
        with self.assertRaises(ValueError): release.validate_residency(row)

    def test_missing_or_wrong_types_fail_cleanly(self):
        for row in (None, [], {}, {'device': 'xpu:2'}):
            with self.subTest(row=row), self.assertRaises(ValueError): release.validate_residency(row)


if __name__ == '__main__':
    unittest.main()
