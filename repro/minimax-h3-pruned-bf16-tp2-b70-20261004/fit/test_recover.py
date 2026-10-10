"""Synthetic CPU checks only; these cannot qualify the real H3 fit."""
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('recover', HERE / 'recover.py')
recover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recover)
import numpy as np
recover.np = np


class RecoveryChecks(unittest.TestCase):
    def test_bf16_ties_even(self):
        x = np.array([0x3f808000,0x3f818000],dtype=np.uint32).view(np.float32)
        np.testing.assert_array_equal(recover.bf16(x).view(np.uint32),[0x3f800000,0x3f820000])

    def test_one_ulp(self):
        r = np.array([1.],np.float16)
        m = recover.metric(np.nextafter(r,np.float16(np.inf)),r,np.float16)
        self.assertFalse(m['bit_exact'])
        self.assertEqual(m['max_reference_ulp'],1.)
        self.assertEqual(m['max_abs'],2**-10)

    def test_signed_zero_is_not_bit_exact(self):
        m = recover.metric(np.array([-0.]),np.array([0.]),np.float32)
        self.assertFalse(m['bit_exact'])
        self.assertEqual(m['max_abs'],0)

    def test_chunk_reader_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'tensor.safetensors'
            a = np.array([[0x3f80,0x4000],[0x4040,0x4080]],dtype='<u2')
            h = json.dumps({'x':dict(dtype='BF16',shape=[2,2],data_offsets=[0,8])}).encode()
            p.write_bytes(struct.pack('<Q',len(h))+h+a.tobytes())
            t = recover.Tensors(p)
            np.testing.assert_array_equal(t.read('x',1,2)[0],[[3.,4.]])
            self.assertEqual(t.inventory('x')['sha256'],recover.sha(a.tobytes()))
            p.write_bytes(p.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError,'Truncated'):
                t.read('x')

    def test_symlink_cannot_enter_protected_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'alias'
            p.symlink_to('/mnt/usb-models/llm-models')
            with self.assertRaises(ValueError):
                recover.safe_path(p/'anything')
        with self.assertRaises(ValueError):
            recover.safe_path('/mnt/fast-ai/result.json',writing=True)
        with self.assertRaises(ValueError):
            recover.safe_path('/dev/dri/renderD128')

    def test_missing_input_never_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            result = subprocess.run([sys.executable,'-B',str(HERE/'recover.py'),
                '--full-dir',str(p/'missing'),'--fitted',str(p/'missing.safetensors'),
                '--receipt',str(p/'receipt.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            r = json.loads((p/'receipt.json').read_text())
            self.assertEqual(r['verdict'],'blocked')
            self.assertIsNone(r['max_abs'])
            self.assertIsNone(r['adaln_bit_exact'])
            self.assertFalse(r['whole_denoiser_bit_exact'])
            self.assertEqual(r['outputs'],[])

    def test_grid_reversal_and_zero_curve(self):
        weights = [np.zeros((3,256),np.float32),np.zeros(3,np.float32),
                   np.zeros((2,3),np.float32),np.array([1.,-1.],np.float32)]
        for precision in ('f32','f64','bf16-io'):
            a = recover.curve(weights,precision)
            b = recover.curve(weights,precision,reverse=True)
            np.testing.assert_array_equal(a,b[::-1])
            self.assertEqual(a.shape,(1025,2))
            np.testing.assert_allclose(a[0],[0.7310586,-0.2689414],atol=0.002)

    def test_full_cli_synthetic_mismatch(self):
        # Real H3 embedder shapes, synthetic zero weights; tiny projection.
        # Exercises the real reader, SVD/solvers and receipt, not H3 correctness.
        def write(path, arrays):
            offset, header = 0, {}
            for key,a in arrays.items():
                header[key] = dict(dtype='F32',shape=list(a.shape),
                                   data_offsets=[offset,offset+a.nbytes])
                offset += a.nbytes
            raw = json.dumps(header).encode()
            with path.open('wb') as f:
                f.write(struct.pack('<Q',len(raw))+raw)
                for a in arrays.values():
                    f.write(a.tobytes())
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            write(p/'official.safetensors',{
                'time_embedder.linear_1.weight':np.zeros((5376,256),np.float32),
                'time_embedder.linear_1.bias':np.zeros(5376,np.float32),
                'time_embedder.linear_2.weight':np.zeros((2688,5376),np.float32),
                'time_embedder.linear_2.bias':np.zeros(2688,np.float32),
                'transformer_blocks.0.adaln_proj.linear.weight':np.zeros((2,2688),np.float32),
                'transformer_blocks.0.adaln_proj.linear.bias':np.zeros(2,np.float32)})
            table = np.zeros((1025,8),np.float32)
            table[:8] = np.eye(8,dtype=np.float32)
            write(p/'fitted.safetensors',{'adaln_t_table':table,
                'blocks.0.adaln_proj.linear.weight':np.zeros((2,8),np.float32),
                'blocks.0.adaln_proj.linear.bias':np.zeros(2,np.float32)})
            result = subprocess.run([sys.executable,'-B',str(HERE/'recover.py'),
                '--full-dir',str(p/'official.safetensors'),'--fitted',str(p/'fitted.safetensors'),
                '--receipt',str(p/'receipt.json'),'--blocks','0','--precisions','f32'],
                capture_output=True,text=True)
            r = json.loads((p/'receipt.json').read_text())
            self.assertEqual(result.returncode,1,r)
            self.assertEqual(len(r['variants']),3)
            self.assertFalse(r['adaln_bit_exact'])
            self.assertFalse(r['whole_denoiser_bit_exact'])
            self.assertTrue(r['inputs'][0]['sha256'])
            for v in r['variants']:
                self.assertFalse(v['table']['bit_exact'])
                self.assertTrue(v['projections'][0]['weight']['bit_exact'])


if __name__ == '__main__':
    unittest.main()
