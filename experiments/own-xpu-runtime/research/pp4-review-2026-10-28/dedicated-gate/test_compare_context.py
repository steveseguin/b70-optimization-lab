"""Small byte-range/shape fixtures only; no model-state parity claimed."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from compare_context import capacity_layout,prefix_zero,TARGET,DRAFT,shape

class ContextTests(unittest.TestCase):
    def layout(self,draft=False):
        width=2 if draft else 4;dtype='BF16' if draft else 'f32'
        kind='keys';name=next(n for n,k in (DRAFT if draft else TARGET).items() if k==kind)
        rows=[]
        for context in (262144,65536):
            s=shape(kind,context);rows.append(dict(dtype=dtype,shape=s,bytes=context*2*256*width))
        return name,*rows
    def test_only_registered_exact_target_and_draft_shapes(self):
        for draft in (False,True):capacity_layout(*self.layout(draft),draft=draft)
        self.assertEqual(len(TARGET),48);self.assertEqual(len(DRAFT),4)
    def test_unregistered_name_refused(self):
        _,a,b=self.layout()
        with self.assertRaisesRegex(ValueError,'unregistered'):capacity_layout('blk.0.other.bin',a,b)
    def test_shape_dtype_and_bytes_refused(self):
        for field,value in (('shape',[65536,4,128]),('dtype','BF16'),('bytes',1)):
            name,a,b=self.layout();b[field]=value
            with self.assertRaisesRegex(ValueError,'shape/dtype/byte'):capacity_layout(name,a,b)
    def ranges(self,tmp,big=b'ABCD'+bytes(12),small=b'ABCD'):
        a=Path(tmp)/'large';b=Path(tmp)/'small';a.write_bytes(big);b.write_bytes(small)
        return a,0,len(big),sha256(big).hexdigest(),b,0,len(small),sha256(small).hexdigest()
    def test_exact_full_prefix_and_zero_tail_preserve_full_hashes(self):
        with TemporaryDirectory() as tmp:
            args=self.ranges(tmp);proof=prefix_zero(*args)
            self.assertEqual(proof['compared_prefix_bytes'],4);self.assertEqual(proof['verified_zero_extra_bytes'],12)
            self.assertEqual(proof['reference_full_sha256'],args[3]);self.assertEqual(proof['candidate_full_sha256'],args[7])
            self.assertNotEqual(proof['reference_full_sha256'],proof['candidate_full_sha256'])
    def test_nonzero_tail_refused(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'nonzero reference'):prefix_zero(*self.ranges(tmp,big=b'ABCD'+bytes(11)+b'X'))
    def test_prefix_mismatch_refused(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'prefix mismatch'):prefix_zero(*self.ranges(tmp,small=b'ABCE'))
    def test_bounds_ratio_and_original_hash_refused(self):
        with TemporaryDirectory() as tmp:
            args=list(self.ranges(tmp))
            for index,value,message in ((1,-1,'bounded prefix'),(2,15,'bounded prefix'),(1,1,'range/file bounds'),(3,'0'*64,'payload hash')):
                changed=deepcopy(args);changed[index]=value
                with self.assertRaisesRegex(ValueError,message):prefix_zero(*changed)
if __name__=='__main__':unittest.main()
