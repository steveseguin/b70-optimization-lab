"""CPU-only packet137 integration, complete-check and code-owner regressions."""
import ast
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import f32_scan137
import stream_receipts
import continuation_anchor
from native_bindings import NativeBindings
import runtime_packet as rp

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / '20261010-continuation135-stream'


class F32Binding137(unittest.TestCase):
    def test_wrappers_preserve_all_exceptions_and_check_each_call(self):
        for module, name, invalid, bad in ((stream_receipts, 'finite_f32', 'F32 bytes required', 'Nonfinite F32 value'),
                (continuation_anchor, 'finite_bytes', 'Immutable complete F32 bytes required', 'Nonfinite anchor')):
            fn = getattr(module, name)
            for mode in ('parent', 'bulk'):
                with patch.object(module, '_F32_SCAN', mode):
                    for raw in (None, bytearray(4), b'x', memoryview(b'1234')):
                        with self.assertRaisesRegex(ValueError, '^' + invalid + '$'):
                            fn(raw)
                    for raw in (b'', struct.pack('<I', 0), struct.pack('<I', 0x80000000), struct.pack('<I', 0x7f7fffff)):
                        self.assertIsNone(fn(raw))
                    for word in (0x7f800000, 0xff800000, 0x7f800001, 0xffffffff):
                        with self.assertRaisesRegex(ValueError, '^' + bad + '$'):
                            fn(struct.pack('<I', word))
            with patch.object(module, '_F32_SCAN', 'bulk'), patch.object(f32_scan137, 'finite', wraps=f32_scan137.finite) as scan:
                fn(b'\0' * 4)
                fn(b'\0' * 4)
                self.assertEqual(scan.call_count, 2)

    def test_runtime_mode_global_resolves_in_constructor_and_prepare(self):
        import integration
        self.assertIs(integration.Runtime.__init__.__globals__['stream_receipts'], stream_receipts)
        self.assertIs(integration.Runtime.prepare.__globals__['stream_receipts'], stream_receipts)
        self.assertEqual(integration.stream_receipts._F32_SCAN, stream_receipts._F32_SCAN)

    def test_receipt_scan_option_accepts_modes_and_refuses_unknown(self):
        from test_timing_split import Validation
        for mode in ('parent', 'bulk'):
            value = Validation().receipt()
            value['server_options']['f32_scan'] = mode
            stream_receipts.validate_measurements(value)
        for mode in (None, True, 0, 'quick', ''):
            value = Validation().receipt()
            value['server_options']['f32_scan'] = mode
            with self.assertRaisesRegex(ValueError, 'Invalid F32 scan mode'):
                stream_receipts.validate_measurements(value)

    def test_decode_and_preview_bind_reported_scan_mode(self):
        receipt = {'server_options': {'f32_scan': 'bulk'}}
        for mode in ('parent', None, 'bogus'):
            value = {'server_options': {'f32_scan': mode}}
            with self.assertRaises(ValueError):
                stream_receipts.validate_f32_scan_record(value, receipt)
        self.assertEqual(stream_receipts.validate_f32_scan_record(receipt, receipt), 'bulk')
        self.assertEqual(stream_receipts.validate_f32_scan_record({}), 'parent')
        with self.assertRaisesRegex(ValueError, 'F32 scan mode differs'):
            stream_receipts.validate_f32_scan_record({}, receipt)

    def test_launch_mode_not_read_per_call(self):
        for module, name in ((stream_receipts, 'finite_f32'), (continuation_anchor, 'finite_bytes')):
            mode = module._F32_SCAN
            with patch.dict(os.environ, LTX_F32_SCAN='invalid'):
                self.assertIsNone(getattr(module, name)(b'\0' * 4))
                self.assertEqual(module._F32_SCAN, mode)

    def test_native_guard_pins_helper_function_owner(self):
        guard = object.__new__(NativeBindings)
        guard.pin = lambda relative: HERE / 'f32_scan137.py'
        binding = guard.bind_module(f32_scan137, 'source/scripts/f32_scan137.py')
        guard.check_module(binding)
        with patch.object(f32_scan137, 'finite', lambda raw: True):
            with self.assertRaisesRegex(RuntimeError, 'Helper function source/code/owner changed: finite'):
                guard.check_module(binding)
        guard.check_module(binding)

    def test_native_guard_pins_helper_function_code(self):
        guard = object.__new__(NativeBindings)
        guard.pin = lambda relative: HERE / 'f32_scan137.py'
        binding = guard.bind_module(f32_scan137, 'source/scripts/f32_scan137.py')
        original = f32_scan137.finite.__code__
        try:
            f32_scan137.finite.__code__ = (lambda raw: True).__code__
            with self.assertRaisesRegex(RuntimeError, 'Helper function source/code/owner changed: finite'):
                guard.check_module(binding)
        finally:
            f32_scan137.finite.__code__ = original
        guard.check_module(binding)

    def test_parent_predicate_is_identical_ast(self):
        for name, func in (('stream_receipts.py', 'finite_f32'), ('continuation_anchor.py', 'finite_bytes')):
            old = next(n for n in ast.parse((PARENT/name).read_text()).body if isinstance(n, ast.FunctionDef) and n.name == func)
            new = next(n for n in ast.parse((HERE/name).read_text()).body if isinstance(n, ast.FunctionDef) and n.name == func)
            choice = new.body[1].value.args[0]
            self.assertIsInstance(choice, ast.IfExp)
            new.body[1].value.args[0] = choice.orelse
            self.assertEqual(ast.dump(old), ast.dump(new))

    def test_bulk_run_name_suffix_and_complete_inventory(self):
        from sealed_import_cpu import production_environment
        env = production_environment()
        env['LTX_F32_SCAN'] = 'parent'
        parent = rp.expected_run_name(env)
        env['LTX_F32_SCAN'] = 'bulk'
        self.assertEqual(rp.expected_run_name(env), parent + '-f32bulk')
        self.assertIn('f32_scan137.py', rp.COMPONENTS)
        self.assertEqual(rp.MODULES['f32_scan137.py'], 'f32_scan137.py')


if __name__ == '__main__':
    unittest.main()
