"""Six-output accounting and refusal using existing fake metadata tensors."""
import hashlib
import importlib.util
from pathlib import Path
import types
import unittest

import capture_adapter as A

SOURCE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/source/scripts/ltx_duration_guard.py')
FIXTURES = Path(__file__).resolve().parent.parent / '20261007-duration110-runtime/test_duration_guard.py'
spec = importlib.util.spec_from_file_location('duration_capture_fixtures', FIXTURES)
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)


class Controls(unittest.TestCase):
    def setUp(self):
        self.d = types.ModuleType('continuation_capture_guard')
        exec(compile(A.transform_guard(SOURCE.read_bytes()), '<inactive111guard>', 'exec'), self.d.__dict__)
        self.rows = [{'name': 'continuation111-pass%d-chunk%d' % (p, c),
                      'graph_sha256': hashlib.sha256(('%d%d' % (p, c)).encode()).hexdigest(), 'role': 'full'}
                     for p in range(2) for c in range(3)]
        self.active = {}
        self.guard = self.d.CaptureGuard('a'*64, self.rows, lambda: dict(self.active))

    def call(self, index, shapes=None):
        row = self.rows[index]
        self.active = {'name': row['name'], 'graph_sha256': row['graph_sha256'],
                       'plan_sha256': 'a'*64, 'prompt_id': 'prompt%d' % index}
        ts = T.tensors(self.d.FULL_SHAPES if shapes is None else shapes)
        return self.guard.validate(ts, T.report(ts, row['name']), row['name'])

    def test_six_full_outputs_reserved_no_seventh_retry_or_refund(self):
        for i in range(6): self.call(i)
        receipt = self.guard.receipt()
        self.assertEqual(receipt['captures_reserved'], 6)
        self.assertEqual(receipt['capture_cap'], 6)
        self.assertEqual(receipt['reserved_bytes'], 877383216)
        self.assertEqual(receipt['reserved_bytes'], receipt['raw_budget_bytes'])
        self.assertEqual(receipt['schema'], 'ltx.continuation111-prewrite.v1')
        with self.assertRaisesRegex(self.d.GuardError, 'exhausted'): self.call(5)
        self.assertEqual(self.guard.receipt()['reserved_bytes'], 877383216)
        with self.assertRaisesRegex(self.d.GuardError, 'already failed'): self.call(5)

    def test_only_six_full_roles_accepted(self):
        for rows in (self.rows[:-1], self.rows + [dict(self.rows[0], name='extra')],
                     [dict(self.rows[0], role='fill')] + self.rows[1:],
                     [dict(self.rows[0], role='setup')] + self.rows[1:]):
            with self.assertRaises(self.d.GuardError):
                self.d.CaptureGuard('a'*64, rows, lambda: {})

    def test_placeholder_and_mixed_shapes_refused_before_charge(self):
        for shapes in (self.d.FILL_SHAPES, {**self.d.FULL_SHAPES, 'images': (1, 8, 8, 3)}):
            self.setUp()
            with self.assertRaisesRegex(self.d.GuardError, 'role/shape'): self.call(0, shapes)
            self.assertEqual(self.guard.receipt()['reserved_bytes'], 0)

    def test_registered_order_and_identity_unchanged(self):
        with self.assertRaisesRegex(self.d.GuardError, 'next registered'): self.call(1)
        self.assertIsNotNone(self.guard.failed)
        self.assertEqual(self.guard.receipt()['captures_reserved'], 0)

    def test_source_pin_and_validation_arithmetic_unchanged(self):
        raw = SOURCE.read_bytes()
        for changed in (raw+b'\n', A.transform_guard(raw)):
            with self.assertRaises(ValueError): A.transform_guard(changed)
        # Exact validation body remains inherited; only construction/counts and
        # reporting differ. Serializer/source transforms also remain unchanged.
        old = raw[raw.index(b'    def validate('):raw.index(b'    def receipt(')]
        out = A.transform_guard(raw)
        self.assertEqual(old, out[out.index(b'    def validate('):out.index(b'    def receipt(')])
        self.assertGreater(len(old), 1000)
        self.assertEqual(self.d.SERIALIZER_SHA256, T.d.SERIALIZER_SHA256)


if __name__ == '__main__': unittest.main()
