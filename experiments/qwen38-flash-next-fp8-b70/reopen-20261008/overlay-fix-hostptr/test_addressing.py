"""CPU NumPy emulation. Never import vLLM, Triton or a device runtime."""
import ast
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PLACEMENT = Path('vllm/q38_expert_placement.py')
KERNEL = Path('vllm/model_executor/layers/fused_moe/fused_moe.py')
MASK = 2**64 - 1


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


original = load(ROOT / 'overlay' / PLACEMENT, 'hostptr_original')
modified = load(HERE / 'modules' / PLACEMENT, 'hostptr_modified')


class AddressingTests(unittest.TestCase):
    def compare(self, resident, host, bases, shape, itemsize=1):
        n, k = shape
        row_elements = n * k
        old = original.offsets(*bases, resident, host, row_elements * itemsize, itemsize)
        local, selector = modified.local_row_tables(resident, host, row_elements)
        selected = np.where(np.asarray(selector, dtype=np.bool_),
                            np.uint64(bases[1]), np.uint64(bases[0]))
        new = selected + np.asarray(local, dtype=np.uint64) * np.uint64(row_elements * itemsize)
        expected = np.asarray([(bases[0] + delta * itemsize) & MASK for delta in old], dtype=np.uint64)
        # Every logical expert and every N row, first and last byte. Equal
        # starts plus unchanged K stride prove every intervening byte address.
        row_offsets = np.arange(n, dtype=np.uint64) * np.uint64(k * itemsize)
        for boundary in (0, k * itemsize - 1):
            np.testing.assert_array_equal(new[:, None] + row_offsets + np.uint64(boundary),
                                          expected[:, None] + row_offsets + np.uint64(boundary))
        for logical, index in enumerate(local):
            self.assertLess(index, len(host if selector[logical] else resident))

    def test_every_registered_rank_layer_expert_and_matrix_row(self):
        for filename in ('placement-certified-v5.json', 'placement-attempt6-v5.json'):
            placement = json.loads((ROOT / filename).read_text())
            for rank in range(4):
                for layer in range(48):
                    resident, host = original.row_plan(placement, rank, layer)
                    for shape in ((1280, 2560), (2560, 640)):
                        self.compare(resident, host, (0x800000000000, 0x200000001000), shape)

    def test_signed_positive_negative_and_wrap_offsets(self):
        for bases in ((0x100000, 0x800000), (0x800000, 0x101000),
                      (0xFFFFFFFFFFF00000, 0x1000), (0x1000, 0xFFFFFFFFFFF00000)):
            for itemsize in (1, 2):
                with self.subTest(bases=bases, itemsize=itemsize):
                    self.compare([0, 2], [1, 3], bases, (16, 256), itemsize)

    def test_all_bytes_match_with_nonzero_host_slab_offset(self):
        slab = (np.arange(3 * 2**20, dtype=np.uint32) % 251).astype(np.uint8)
        host = slab[4096:4096 + 3 * 4096].reshape(3, 16, 256)
        resident = (np.arange(2 * 4096, dtype=np.uint32) % 239).astype(np.uint8).reshape(2, 16, 256)
        resident_rows, host_rows = [0, 3], [1, 2, 4]
        local, selector = modified.local_row_tables(resident_rows, host_rows, 4096)
        # Virtual aligned bases let NumPy allocation alignment be irrelevant.
        rb, slab_base = 0x800000, 0x200000
        hb = slab_base + 4096
        old = original.offsets(rb, hb, resident_rows, host_rows, 4096, 1)
        for expert in range(5):
            tensor, base = (host, hb) if selector[expert] else (resident, rb)
            columns = np.arange(4096, dtype=np.uint64)
            new_addresses = np.uint64(base + local[expert] * 4096) + columns
            old_addresses = np.uint64((rb + old[expert]) & MASK) + columns
            np.testing.assert_array_equal(new_addresses, old_addresses)
            indices = (old_addresses - np.uint64(base)).astype(np.int64)
            np.testing.assert_array_equal(tensor[local[expert]].ravel(), tensor.ravel()[indices])

    def test_reject_invalid_partition_and_alignment(self):
        for args in (([0], [0], 256), ([0], [2], 256), ([0], [1], 257), ([0], [], 0)):
            with self.assertRaises(ValueError):
                modified.local_row_tables(*args)

    def test_empty_host_and_empty_resident_math(self):
        for resident, host in (([0, 1], []), ([], [0, 1])):
            self.compare(resident, host, (0x10000, 0x20000), (16, 256))

    def test_storage_snapshot_detects_mutable_alias_drift(self):
        class Tensor:
            def __init__(self, ptr):
                self.ptr, self.shape, self.dtype, self.device = ptr, (2, 16, 256), 'uint8', 'xpu:0'
            def data_ptr(self): return self.ptr
            def stride(self): return (4096, 256, 1)
        resident, host, uva = Tensor(8192), Tensor(16384), Tensor(16384)
        resident._q38_host_cpu, resident._q38_host_storage = host, uva
        resident._q38_storage_facts = modified.storage_facts(resident, host, uva)
        modified.validate_hostptr_storage(resident)
        for tensor in (resident, host, uva):
            tensor.ptr += 256
            with self.assertRaisesRegex(RuntimeError, 'storage changed'):
                modified.validate_hostptr_storage(resident)
            tensor.ptr -= 256

    def test_restore_preserves_new_tables_and_snapshot(self):
        class Tensor:
            shape = (2, 16, 256)
            def data_ptr(self): return 8192
        saved, current = Tensor(), Tensor()
        for field in ('_q38_row_map', '_q38_host_cpu', '_q38_host_storage', '_q38_num_experts',
                      '_q38_base_table', '_q38_local_row_table', '_q38_is_host_table', '_q38_storage_facts'):
            setattr(saved, field, object())
        layer = SimpleNamespace(w13_weight=current, _q38_placed_w13_weight=saved)
        modified.restore(layer)
        self.assertIs(current._q38_local_row_table, saved._q38_local_row_table)
        self.assertIs(current._q38_is_host_table, saved._q38_is_host_table)
        self.assertIs(current._q38_storage_facts, saved._q38_storage_facts)

    def test_kernel_kn_and_fp8_arithmetic_unchanged(self):
        before = (ROOT / 'overlay' / KERNEL).read_text()
        after = (HERE / 'modules' / KERNEL).read_text()
        begin = '    if off_experts == -1:\n'
        end = '\ndef invoke_fused_moe_wna16_cuda_kernel('
        # Include sentinel handling, descriptors, all K/N math, FP8 dot and stores.
        self.assertEqual(before[before.index(begin, before.index('def fused_moe_kernel(')):before.index(end)],
                         after[after.index(begin, after.index('def fused_moe_kernel(')):after.index(end)])
        self.assertIn('tl.where(is_host, b_host_ptr, b_ptr)', after)
        self.assertIn('tl.maximum(off_experts, 0)', after)
        self.assertNotIn('b_table_ptr', after)
        self.assertIn('B if _q38_host is None else _q38_host,', after)

    def test_source_pins_and_exact_patch(self):
        manifest = json.loads((ROOT / 'overlay-manifest.json').read_text())
        expected = []
        for relative in sorted((PLACEMENT, KERNEL)):
            old = ROOT / 'overlay' / relative
            new = HERE / 'modules' / relative
            self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(), manifest['files'][str(relative)])
            ast.parse(new.read_text())
            expected.extend(difflib.unified_diff(old.read_text().splitlines(True), new.read_text().splitlines(True),
                                                fromfile='a/' + str(relative), tofile='b/' + str(relative)))
        self.assertEqual((HERE / 'explicit-host-pointer.patch').read_text(), ''.join(expected))


if __name__ == '__main__':
    unittest.main()
