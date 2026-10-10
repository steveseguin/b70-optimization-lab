"""CPU-only execution of the transformed capture writer with fake tensor math."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

import evidence129
import evidence_publication


PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-128')


class Tensor:
    dtype = 'torch.float32'
    shape = (2,)
    def detach(self): return self
    def cpu(self): return self
    def contiguous(self): return self
    def view(self, dtype): return self
    def numpy(self): return self
    def tobytes(self): return struct.pack('<ff', 1., 2.)
    def min(self): return 1.
    def max(self): return 2.
    def float(self): return self
    def std(self): return 0.7071067690849304


class CapturePublication129(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ltx129-capture-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.original = (PARENT / 'source/scripts/capture_node.py').read_bytes()
        self.saved = b'complete-safetensors-serializer-output'
        self.prewrite = mock.Mock()
        torch = types.SimpleNamespace(uint8='uint8',
            are_deterministic_algorithms_enabled=lambda: True,
            is_deterministic_algorithms_warn_only_enabled=lambda: False,
            isfinite=lambda tensor: types.SimpleNamespace(all=lambda: True))
        fake_web = types.SimpleNamespace(middleware=lambda fn: fn)
        self.serializer = mock.Mock(side_effect=lambda tensors, path: Path(path).write_bytes(self.saved))
        modules = {'torch': torch,
            'folder_paths': types.SimpleNamespace(get_output_directory=lambda: str(self.root)),
            'safetensors.torch': types.SimpleNamespace(save_file=self.serializer),
            'ltx_duration_guard': types.SimpleNamespace(require_capture_prewrite=self.prewrite),
            'aiohttp': types.SimpleNamespace(web=fake_web),
            'server': types.SimpleNamespace(PromptServer=types.SimpleNamespace(
                instance=types.SimpleNamespace(app=types.SimpleNamespace(middlewares=[]))))}
        self.module = types.ModuleType('capture129_cpu_test')
        with mock.patch.dict(sys.modules, modules):
            exec(compile(evidence129.transform_capture(self.original), '<capture129>', 'exec'), self.module.__dict__)
        self.capture = self.module.LTXBaselineCapture().capture
        self.out = self.root / 'validation/case'

    def run_capture(self):
        tensor = Tensor()
        return self.capture(tensor, {'samples': tensor}, {'samples': tensor},
                            {'waveform': tensor, 'sample_rate': 24000}, 'case')

    def test_complete_capture_and_summary_bytes_and_hashes(self):
        result = self.run_capture()
        self.assertEqual((self.out / 'tensors.safetensors').read_bytes(), self.saved)
        report = self.prewrite.call_args.args[1]
        self.assertEqual((self.out / 'summary.json').read_bytes(),
                         (json.dumps(report, indent=2) + '\n').encode())
        for row in report['tensors'].values():
            self.assertEqual(row['sha256'], hashlib.sha256(Tensor().tobytes()).hexdigest())
        self.assertEqual(result['ui']['text'], [str(self.out / 'summary.json')])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ['summary.json', 'tensors.safetensors'])

    def test_partial_serializer_never_exposes_final_capture(self):
        def serialize(tensors, path):
            path = Path(path)
            path.write_bytes(self.saved[:5])
            self.assertFalse((self.out / 'tensors.safetensors').exists())
            self.assertFalse((self.out / 'summary.json').exists())
            with path.open('ab') as stream:
                stream.write(self.saved[5:])
        self.serializer.side_effect = serialize
        self.run_capture()
        self.assertEqual((self.out / 'tensors.safetensors').read_bytes(), self.saved)

    def test_before_publication_final_is_absent(self):
        publish = evidence_publication.publish_file
        def observe(temporary, final):
            self.assertEqual(Path(temporary).parent, Path(final).parent)
            self.assertFalse(Path(final).exists())
            if Path(final).name == 'tensors.safetensors':
                self.assertEqual(Path(temporary).read_bytes(), self.saved)
            else:
                self.assertEqual(json.loads(Path(temporary).read_bytes())['run_name'], 'case')
            return publish(temporary, final)
        with mock.patch.object(evidence_publication, 'publish_file', side_effect=observe):
            self.run_capture()

    def test_failed_serializer_cleans_private_file_and_leaves_no_final(self):
        def fail(tensors, path):
            Path(path).write_bytes(b'partial')
            raise RuntimeError('serializer failed')
        self.serializer.side_effect = fail
        with self.assertRaisesRegex(RuntimeError, 'serializer failed'):
            self.run_capture()
        self.assertEqual(list(self.out.iterdir()), [])

    def test_prewrite_gate_still_precedes_directory_and_serializer(self):
        self.prewrite.side_effect = RuntimeError('capture refused')
        with self.assertRaisesRegex(RuntimeError, 'capture refused'):
            self.run_capture()
        self.assertFalse(self.out.exists())
        self.serializer.assert_not_called()

    def test_duplicate_capture_never_overwrites_committed_bytes(self):
        self.run_capture()
        original = {p.name: p.read_bytes() for p in self.out.iterdir()}
        with self.assertRaises(FileExistsError):
            self.run_capture()
        self.assertEqual({p.name: p.read_bytes() for p in self.out.iterdir()}, original)

    def test_unknown_parent_writer_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'parent differs'):
            evidence129.transform_capture(self.original.replace(b'save_file(tensors,', b'other_writer(tensors,'))


if __name__ == '__main__':
    unittest.main()
