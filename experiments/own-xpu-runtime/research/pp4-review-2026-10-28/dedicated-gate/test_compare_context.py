"""Small byte-range/shape fixtures only; no model-state parity claimed."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import math
from compare_context import capacity_layout,prefix_zero,TARGET,DRAFT,shape,draft_identity

class ContextTests(unittest.TestCase):
    def test_only_actual_context_difference_allowed(self):
        a=dict(context=262144,pair_sequence_sha256='actual',position=1707,arithmetic='exact')
        b=dict(a,context=65536)
        draft_identity(a,b,'actual')
        for changed in (dict(b,context=262144),dict(b,position=1706),dict(b,arithmetic='other'),dict(b,extra=True)):
            with self.assertRaises(ValueError):draft_identity(a,changed,'actual')
        with self.assertRaises(ValueError):draft_identity(a,b,'fabricated')
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
    def test_128k_layout_requires_explicit_matching_capacity(self):
        for draft,registry in ((False,TARGET),(True,DRAFT)):
            width,dtype=(2,'BF16') if draft else (4,'f32')
            for name,kind in registry.items():
                rows=[dict(dtype=dtype,shape=shape(kind,c),bytes=math.prod(shape(kind,c))*width)
                      for c in (262144,131072)]
                capacity_layout(name,*rows,draft=draft,candidate_context=131072)
                with self.assertRaises(ValueError):capacity_layout(name,*rows,draft=draft)
        a=dict(context=262144,pair_sequence_sha256='actual')
        b=dict(a,context=131072)
        draft_identity(a,b,'actual',candidate_context=131072)
        with self.assertRaises(ValueError):draft_identity(a,b,'actual')
    def test_128k_ratio_still_checks_all_prefix_and_extra_tail(self):
        with TemporaryDirectory() as tmp:
            args=self.ranges(tmp,big=b'ABCD'+bytes(4))
            proof=prefix_zero(*args,ratio=2)
            self.assertEqual(proof['verified_zero_extra_bytes'],4)
            for ratio in (4,True,1,8):
                with self.assertRaises(ValueError):prefix_zero(*args,ratio=ratio)
            with self.assertRaisesRegex(ValueError,'nonzero reference'):
                prefix_zero(*self.ranges(tmp,big=b'ABCD'+bytes(3)+b'X'),ratio=2)
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
