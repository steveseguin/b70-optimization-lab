"""CPU fake allocator tests: no device import, launch or numerical waiver."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import allocator_release130 as release
import display_replica as replica

GIB = 2 ** 30
FREE = 8465399808
REQUIRED = 37 * GIB // 4
SCOPE = {'LTX_DISPLAY_ALLOCATOR_RELEASE': 'before-admission',
         'LTX_STREAM_FRAMES': '169', 'LTX_SAMPLER_PLACEMENT': 'two-way20-28',
         'LTX_ANCHOR': 'frame', 'LTX_DECODER_GRAPH': '0',
         'LTX_ANCHOR_DECODE': 'cone', 'LTX_BENCODE_OVERLAP': '1',
         'LTX_PREP_AHEAD': '1', 'LTX_DISPLAY_DEVICE': 'xpu:2',
         'LTX_DISPLAY_SCHEDULE': 'eager-display', 'LTX_DISPLAY_WORKER': 'parallel',
         'LTX_AUX_RESIDENCY': 'legacy', 'LTX_SNAPSHOT_MODE': 'fingerprint',
         'LTX_SNAPSHOT_SCHEDULE': 'full', 'LTX_ANCHOR_READ_AHEAD': '0'}


def fake(gain=3*GIB//2, release_error=None, reservation_gain=None):
    state = {'calls': 0}
    def empty():
        state['calls'] += 1
        if release_error:
            raise release_error
    xpu = SimpleNamespace(empty_cache=Mock(side_effect=empty),
        mem_get_info=lambda card: (FREE + gain * bool(state['calls']), 32*GIB),
        memory_allocated=lambda card: 18*GIB,
        memory_reserved=lambda card: 22*GIB - (gain if reservation_gain is None else reservation_gain)*bool(state['calls']),
        max_memory_allocated=lambda card: 23*GIB)
    torch = SimpleNamespace(xpu=xpu)
    return torch, lambda: xpu.mem_get_info('xpu:2')[0]


class AllocatorRelease(unittest.TestCase):
    def run_admission(self, torch, free, mode='before-admission', required=REQUIRED):
        return release.before_admission(torch, free, mode=mode, required_bytes=required, phase='before-decode')

    def owner(self, gain):
        torch, free = fake(gain)
        obj = replica.ResidentDisplay.__new__(replica.ResidentDisplay)
        obj.torch, obj.free_bytes = torch, free
        obj.transient_bytes, obj.screening_bytes = 13*GIB//2, 3*GIB//4
        obj.allocator_release_mode = 'before-admission'
        return obj

    def test_default_off(self):
        self.assertEqual(release.launch_mode({}), 'off')
        self.assertEqual(release.validate_scope({}), 'off')

    def test_invalid_modes(self):
        for mode in ('', 'on', True, None, 'before-admission '):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                release.launch_mode({release.ENV: mode})

    def test_enabled_scope(self):
        self.assertEqual(release.validate_scope(SCOPE), 'before-admission')

    def test_each_scope_field_is_required(self):
        for key in SCOPE:
            if key == release.ENV:
                continue
            env = dict(SCOPE); del env[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.validate_scope(env)

    def test_each_wrong_scope_field_refuses(self):
        for key in SCOPE:
            env = dict(SCOPE, **{key: 'wrong'})
            with self.subTest(key=key), self.assertRaises(ValueError):
                release.validate_scope(env)

    def test_off_calls_no_allocator_api(self):
        free = Mock(return_value=FREE)
        actual, record = self.run_admission(None, free, mode='off')
        self.assertEqual(actual, FREE); self.assertIsNone(record)
        free.assert_called_once_with()

    def test_sufficient_free_does_not_release(self):
        torch, _ = fake()
        actual, record = self.run_admission(torch, lambda: REQUIRED)
        self.assertEqual(actual, REQUIRED); self.assertFalse(record['release_called'])
        torch.xpu.empty_cache.assert_not_called()

    def test_one_release_uses_new_physical_reading(self):
        torch, free = fake()
        actual, record = self.run_admission(torch, free)
        self.assertEqual(actual, FREE+3*GIB//2)
        torch.xpu.empty_cache.assert_called_once_with()
        self.assertEqual(record['physical_free_delta_bytes'], 3*GIB//2)
        self.assertEqual(len(record['before']), 4)
        self.assertEqual(record['scope'], 'process-wide XPU allocator')
        self.assertTrue(record['reclaim_is_not_guaranteed'])

    def test_reserved_release_is_not_physical_credit(self):
        torch, free = fake(0, reservation_gain=3*GIB)
        actual, record = self.run_admission(torch, free)
        self.assertEqual(actual, FREE)
        self.assertEqual(record['reserved_released_bytes_by_card']['xpu:2'], 3*GIB)
        torch.xpu.empty_cache.assert_called_once_with()

    def test_zero_release_still_refuses(self):
        obj = self.owner(0)
        with self.assertRaisesRegex(RuntimeError, 'Display replica refuses.*allocator_release='):
            obj.admit('before-decode')
        obj.torch.xpu.empty_cache.assert_called_once_with()

    def test_point_eight_is_insufficient_for_screen(self):
        obj = self.owner(int(.8*GIB))
        with self.assertRaisesRegex(RuntimeError, 'Display replica refuses'):
            obj.admit('before-decode')

    def test_one_point_five_passes_unchanged_budget(self):
        obj = self.owner(3*GIB//2)
        result = obj.admit('before-decode')
        self.assertGreaterEqual(result['margin_bytes'], obj.screening_bytes)
        self.assertEqual(result['transient_budget_bytes'], 13*GIB//2)
        self.assertEqual(result['floor_bytes'], 2*GIB)

    def test_exact_screen_boundary(self):
        obj = self.owner(REQUIRED-FREE)
        self.assertEqual(obj.admit('before-decode')['margin_bytes'], 3*GIB//4)

    def test_one_byte_below_screen_refuses(self):
        obj = self.owner(REQUIRED-FREE-1)
        with self.assertRaises(RuntimeError): obj.admit('before-decode')

    def test_new_weights_count_before_install(self):
        obj = self.owner(3*GIB//2)
        with self.assertRaises(RuntimeError): obj.admit('before-install', 834267746)

    def test_off_preserves_original_budget_exception(self):
        obj = self.owner(3*GIB//2); obj.allocator_release_mode = 'off'
        with self.assertRaises(RuntimeError) as got: obj.admit('before-decode')
        self.assertNotIn('allocator_release', str(got.exception))
        obj.torch.xpu.empty_cache.assert_not_called()

    def test_release_exception_propagates_once(self):
        torch, free = fake(release_error=RuntimeError('release failed'))
        with self.assertRaisesRegex(RuntimeError, 'release failed'):
            self.run_admission(torch, free)
        torch.xpu.empty_cache.assert_called_once_with()

    def test_facts_rechecked_after_release(self):
        obj = self.owner(3*GIB//2); obj.baseline = ('immutable',)
        obj.check = Mock(side_effect=RuntimeError('Display replica residency/weights changed'))
        with self.assertRaisesRegex(RuntimeError, 'weights changed'): obj.admit('before-decode')
        obj.check.assert_called_once_with()

    def test_invalid_free_refuses_before_release(self):
        for value in (-1, True, 2.0, None):
            torch, _ = fake()
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.run_admission(torch, lambda: value)
            torch.xpu.empty_cache.assert_not_called()

    def test_bad_counter_refuses_before_release(self):
        torch, free = fake(); torch.xpu.memory_reserved = lambda card: 1
        with self.assertRaisesRegex(RuntimeError, 'census'): self.run_admission(torch, free)
        torch.xpu.empty_cache.assert_not_called()

    def test_negative_actual_delta_is_not_hidden(self):
        torch, free = fake(-GIB//2)
        actual, record = self.run_admission(torch, free)
        self.assertEqual(record['physical_free_delta_bytes'], -GIB//2)
        self.assertEqual(actual, FREE-GIB//2)

    def test_off_never_adds_an_extra_model_check(self):
        obj = self.owner(0); obj.free_bytes = lambda: 20*GIB
        obj.allocator_release_mode = 'off'; obj.baseline = (); obj.check = Mock()
        result = obj.admit('before-decode')
        obj.check.assert_not_called()
        self.assertNotIn('allocator_release', result)


if __name__ == '__main__':
    unittest.main()
