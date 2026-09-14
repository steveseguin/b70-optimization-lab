"""CPU checks for asynchronous trace attribution and overlapping intervals."""
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('analysis', Path(__file__).with_name('analyze-fp8-prefill-trace.py'))
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def event(name, cat, start, duration, ident=None, **args):
    if ident is not None:
        args['External id'] = ident
    return {'name': name, 'cat': cat, 'ph': 'X', 'pid': 1, 'tid': 1,
            'ts': start, 'dur': duration, 'args': args}


class TraceAnalysisTests(unittest.TestCase):
    def analyze(self, events):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rank0.pt.trace.json.gz'
            raw = gzip.compress(json.dumps({'record_shapes': 1, 'distributedInfo': {'rank': 0},
                                            'traceEvents': events}).encode())
            path.write_bytes(raw)
            result = analysis.rank_analysis(path)
            self.assertEqual(path.read_bytes(), raw)
            return result

    def test_async_device_parentage_and_similarly_named_fusion(self):
        result = self.analyze([
            event('vllm::xpu_fp16_linear_rowchunk', 'cpu_op', 0, 10, 1),
            event('aten::mm', 'cpu_op', 1, 2, 2, **{'Input Dims': [[32, 4], [4, 8]]}),
            event('triton_fused_xpu_fp16_linear_rowchunk_4', 'cpu_op', 11, 2, 3),
            event('gemm', 'kernel', 100, 5, 2),
            event('unrelated_fusion', 'kernel', 200, 7, 3)])
        group = result['inclusive_groups']['fp16_rowchunk']
        self.assertEqual(group['root_cpu_call_count'], 1)
        self.assertEqual(group['including_descendant_device']['kernel_sum_ms'], 0.005)
        self.assertEqual(result['operator_shapes'][0]['calls_within_fp16_rowchunk'], 1)

    def test_unique_runtime_correlation_and_ambiguous_correlation(self):
        result = self.analyze([
            event('aten::mm', 'cpu_op', 0, 2, 1),
            event('aten::cat', 'cpu_op', 3, 2, 2),
            event('launch', 'xpu_runtime', 0, 1, 1, correlation=20),
            event('launch', 'xpu_runtime', 0, 1, 1, correlation=21),
            event('launch', 'xpu_driver', 0, 1, 2, correlation=21),
            event('kernel', 'kernel', 100, 5, correlation=20),
            event('unknown', 'kernel', 200, 7, correlation=21)])
        self.assertEqual(result['attribution_kernel_counts'], {'unique_runtime_correlation': 1, 'unattributed': 1})
        self.assertEqual(result['operator_summary'][0]['direct_device']['kernel_sum_ms'], 0.005)
        self.assertEqual(result['device_kernel_sum_ms'], 0.012)

    def test_interval_union_does_not_double_count_overlap(self):
        events = [event('', 'kernel', 0, 10), event('', 'kernel', 5, 10), event('', 'kernel', 20, 5)]
        self.assertEqual(analysis.duration_ms(events), 0.025)
        self.assertEqual(analysis.union_ms(events), 0.020)

    def test_ambiguous_external_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous CPU'):
            self.analyze([event('aten::mm', 'cpu_op', 0, 1, 1),
                          event('aten::cat', 'cpu_op', 2, 1, 1),
                          event('kernel', 'kernel', 5, 1, 1)])


if __name__ == '__main__':
    unittest.main()
