"""CPU-only tests; no torch, vLLM or device imports."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import operator_gate as gate


class OperatorTests(unittest.TestCase):
    def test_actual_methods_full_byte_matrix(self):
        result = gate.cpu_gate()
        self.assertTrue(result['passed'])
        self.assertFalse(result['device_qualified'])
        self.assertEqual(result['case_count'], 144)
        self.assertEqual(len({r['variant'] for r in result['cases']}), 12)
        self.assertEqual(len({r['pattern'] for r in result['cases']}), 12)

    def test_gate_import_and_cpu_path_have_no_runtime_imports(self):
        import ast
        source = ast.parse(Path(gate.__file__).read_text())
        runtime = {'torch', 'vllm', 'triton'}
        for node in source.body:
            if isinstance(node, ast.Import):
                self.assertFalse({a.name.split('.')[0] for a in node.names} & runtime)
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or '').split('.')[0], runtime)
        result = gate.cpu_gate()
        self.assertTrue(result['passed'])

    def test_byte_view_storage_offset_and_alias(self):
        data = gate.payload(4, 2, 2560)
        value = gate.ByteTensor(data, (2, 2560))
        row = value[1:2]
        self.assertEqual(row.offset, 5120)
        self.assertEqual(row.raw(), data[5120:])
        clone = value.clone()
        self.assertIsNot(value.backing, clone.backing)
        clone.backing[5120] ^= 1
        self.assertEqual(value.raw(), data)
        self.assertNotEqual(clone.raw(), data)

    def test_special_payload_bits_survive(self):
        for pattern, (_, words) in enumerate(gate.PATTERNS):
            actual = gate.payload(pattern, 1, 2560)
            self.assertEqual(actual[:2], words[0].to_bytes(2, 'little'))
        self.assertEqual(gate.payload(1, 1, 2560)[:2], b'\x00\x80')
        self.assertEqual(gate.payload(10, 1, 2560)[:2], b'\xc1\x7f')
        self.assertNotEqual(gate.payload(4, 2, 2560, 0), gate.payload(4, 2, 2560, 1))

    def test_candidate_input_mutation_is_detected(self):
        old, new = gate.sources()
        bad = new.replace('output = input_.clone()', 'output = input_', 1)
        with patch.object(gate, 'sources', return_value=(old, bad)):
            with self.assertRaisesRegex(RuntimeError, 'input changed'):
                gate.cpu_gate()

    def test_candidate_row_order_is_detected(self):
        old, new = gate.sources()
        bad = new.replace('for row in range(2):', 'for row in (1, 0):', 1)
        with patch.object(gate, 'sources', return_value=(old, bad)):
            with self.assertRaisesRegex(RuntimeError, 'byte/row/call mismatch'):
                gate.cpu_gate()

    def test_candidate_fallback_corruption_is_detected(self):
        old, new = gate.sources()
        bad = new.replace('output[row : row + 1].copy_(row_out)', 'pass')
        with patch.object(gate, 'sources', return_value=(old, bad)):
            with self.assertRaisesRegex(RuntimeError, 'byte/row/call mismatch'):
                gate.cpu_gate()

    def test_candidate_extra_clone_is_detected(self):
        old, new = gate.sources()
        bad = new.replace('output = input_.clone()', 'output = input_.clone().clone()', 1)
        with patch.object(gate, 'sources', return_value=(old, bad)):
            with self.assertRaisesRegex(RuntimeError, 'candidate copy counts'):
                gate.cpu_gate()

    def test_hook_runs_before_warmup_once_and_is_idempotent(self):
        events = []
        class Worker:
            def compile_or_warm_up_model(self):
                events.append('warmup')
                return 42
        run = lambda comm, directory: events.append((comm, directory))
        gate.patch_worker(Worker, lambda: 'existing TP', '/retained', run)
        gate.patch_worker(Worker, lambda: 'unused', '/unused', run)
        worker = Worker()
        self.assertEqual(worker.compile_or_warm_up_model(), 42)
        self.assertEqual(events, [('existing TP', '/retained'), 'warmup'])
        with self.assertRaisesRegex(RuntimeError, 'only once'):
            worker.compile_or_warm_up_model()

    def test_failed_operator_prevents_warmup(self):
        events = []
        class Worker:
            def compile_or_warm_up_model(self):
                events.append('warmup')
        def fail(*args):
            raise RuntimeError('mismatch')
        gate.patch_worker(Worker, lambda: object(), '/retained', fail)
        with self.assertRaisesRegex(RuntimeError, 'mismatch'):
            Worker().compile_or_warm_up_model()
        self.assertEqual(events, [])

    def test_control_install_is_inert(self):
        with patch.dict('os.environ', {'Q38_M2_GLUE_ROW_COPY': '0'}, clear=True):
            gate.install()

    def test_candidate_missing_receipt_directory_refuses_before_import(self):
        with patch.dict('os.environ', {'Q38_M2_GLUE_ROW_COPY': '1'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'receipt directory'):
                gate.install()

    def receipts(self, directory):
        cases = [dict(rows=m, pattern=pattern, phase=phase, replay_index=repeat,
                      passed=True, input_immutable=True, output_fresh=True,
                      row_sha256_reference=['a' * 64] * m,
                      row_sha256_candidate=['a' * 64] * m, input_sha256='b' * 64)
                 for m in (1, 2) for pattern, _ in gate.PATTERNS
                 for phase, repeat in (('eager', None),
                     ('graph_replay_changed_input', 0), ('graph_replay_changed_input', 1))]
        metadata = []
        for label in ('reference', 'candidate'):
            for m in (1, 2):
                offsets = [0, 5120] if m == 2 and label == 'candidate' else [0] * m
                calls = [dict(shape=[1, 2560], stride=[2560, 1], storage_offset_bytes=offset,
                              payload_bytes=5120, alignment_mod256=0, same_group=True)
                         for offset in offsets]
                metadata.extend([dict(path=label, rows=m, calls=calls)] * 13)
        record = dict(schema='a367-glue01-device-operator.v1', passed=True,
                      all_ranks_passed=True, case_count=72,
                      cases=cases, patch_sha256=gate.PATCH_SHA,
                      candidate_sha256=gate.CANDIDATE_SHA, clean_sha256=gate.CLEAN_SHA,
                      ccl_environment=gate.CCL_ENV,
                      graph_sizes=[1, 2], collective_metadata=metadata, failures=[])
        paths = []
        for rank in range(4):
            path = Path(directory) / f'operator-rank-{rank}.json'
            path.write_text(json.dumps(dict(record, rank=rank)))
            paths.append(path)
        return paths

    def test_four_rank_receipts_required(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.receipts(directory)
            self.assertEqual(len(gate.validate_receipts(directory)), 4)
            paths[3].unlink()
            with self.assertRaises(FileNotFoundError):
                gate.validate_receipts(directory)

    def test_forged_incomplete_or_failed_receipt_refuses(self):
        mutations = ({'passed': False}, {'all_ranks_passed': False},
                     {'case_count': 47}, {'graph_sizes': [2]},
                     {'patch_sha256': 'changed'}, {'cases': []},
                     {'candidate_sha256': 'different-rank'},
                     {'ccl_environment': {}}, {'rank': 1}, {'failures': ['mismatch']},
                     {'collective_metadata': []}, {'clean_sha256': 'changed'})
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                paths = self.receipts(directory)
                record = json.loads(paths[0].read_text())
                record.update(mutation)
                paths[0].write_text(json.dumps(record))
                with self.assertRaises(RuntimeError):
                    gate.validate_receipts(directory)

    def test_duplicate_case_matrix_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.receipts(directory)
            record = json.loads(paths[0].read_text())
            record['cases'][1] = record['cases'][0]
            paths[0].write_text(json.dumps(record))
            with self.assertRaisesRegex(RuntimeError, 'matrix'):
                gate.validate_receipts(directory)

    def test_bad_byte_evidence_refuses(self):
        mutations = ({'input_immutable': False}, {'output_fresh': False},
                     {'row_sha256_reference': ['a' * 64, 'a' * 64]},
                     {'row_sha256_candidate': ['c' * 64]}, {'input_sha256': None})
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                paths = self.receipts(directory)
                record = json.loads(paths[0].read_text())
                record['cases'][0].update(mutation)
                paths[0].write_text(json.dumps(record))
                with self.assertRaises(RuntimeError):
                    gate.validate_receipts(directory)

    def test_repeated_graph_nondeterminism_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.receipts(directory)
            record = json.loads(paths[0].read_text())
            record['cases'][2]['row_sha256_reference'] = ['c' * 64]
            record['cases'][2]['row_sha256_candidate'] = ['c' * 64]
            paths[0].write_text(json.dumps(record))
            with self.assertRaisesRegex(RuntimeError, 'nondeterminism'):
                gate.validate_receipts(directory)

    def test_bad_offset_metadata_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.receipts(directory)
            record = json.loads(paths[0].read_text())
            row = next(e for e in record['collective_metadata']
                       if e['path'] == 'candidate' and e['rows'] == 2)
            row['calls'][1]['storage_offset_bytes'] = 0
            paths[0].write_text(json.dumps(record))
            with self.assertRaisesRegex(RuntimeError, 'shape/stride/offset/group'):
                gate.validate_receipts(directory)


if __name__ == '__main__':
    unittest.main()
