"""Original logical field packers for newly admitted mixed-UD formats.

Expected arrays come from unpacked logical indices/scales/signs. Normative
codebooks are format data; all field placement and tests are independently
written. No model or external runtime is needed by this suite.
"""
import struct
import unittest

import torch
from loaders.dequant import (BY_NAME, IQ2_S_GRID, IQ3_S_GRID, IQ4,
                             dequant_block, dequantize)


def pack_logical(kind, indices, scales, signs, d=0.125):
    b=bytearray(BY_NAME[kind][1])
    b[:2]=struct.pack('<e',d)
    d=struct.unpack('<e',b[:2])[0]
    if kind=='IQ4_NL':
        for lane in range(16):
            b[2+lane]=indices[lane] | (indices[lane+16]<<4)
        expected=torch.tensor([IQ4[q] for q in indices],dtype=torch.float32)*d
    else:
        iq2=kind=='IQ2_S'
        width,grid=(8,IQ2_S_GRID) if iq2 else (4,IQ3_S_GRID)
        # Emit low bytes in logical code order, then high bits by byte/plane.
        b[2:2+len(indices)]=bytes(q%256 for q in indices)
        per_high=4 if iq2 else 8
        bits=2 if iq2 else 1
        for group in range(8):
            b[66+group]=sum((indices[group*per_high+p]//256)<<(bits*p)
                           for p in range(per_high))
        sign_start=34 if iq2 else 74
        b[sign_start:sign_start+32]=bytes(signs)
        scale_start=74 if iq2 else 106
        for pair in range(len(scales)//2):
            b[scale_start+pair]=scales[pair*2] | (scales[pair*2+1]<<4)
        values=[v for q in indices for v in grid[q].to_bytes(width,'little')]
        scale_values=[]
        for scale in scales:
            # Independent tensor arithmetic explicitly rounds each operation.
            multiplier=torch.tensor(d,dtype=torch.float32)
            multiplier=multiplier*(scale+0.5 if iq2 else 1+2*scale)
            if iq2: multiplier=multiplier*0.25
            scale_values.extend([multiplier.item()]*(16 if iq2 else 32))
        sign_values=[-1 if mask&(1<<bit) else 1 for mask in signs for bit in range(8)]
        expected=(torch.tensor(scale_values,dtype=torch.float32)*
                  torch.tensor(values,dtype=torch.float32))*torch.tensor(sign_values,dtype=torch.float32)
    return bytes(b),expected.tolist()


def logical_fixture(kind):
    if kind=='IQ4_NL':
        return pack_logical(kind,[(lane*7+lane//16)%16 for lane in range(32)],[],[])
    iq2=kind=='IQ2_S'
    indices=[(i*79+357)%(1024 if iq2 else 512) for i in range(32 if iq2 else 64)]
    scales=[(i*7+3)%16 for i in range(16 if iq2 else 8)]
    signs=[(i*67+17)%256 for i in range(32)]
    return pack_logical(kind,indices,scales,signs)


class MixedUDDequant(unittest.TestCase):
    def assert_bits(self,kind,data,expected):
        actual=dequant_block(kind,data)
        self.assertEqual(actual.device.type,'cpu')
        self.assertTrue(torch.equal(actual.view(torch.int32),
                                   torch.tensor(expected,dtype=torch.float32).view(torch.int32)))

    def test_every_codebook_entry_every_high_bit_plane(self):
        for kind,total,n,scales in [('IQ2_S',1024,32,16),('IQ3_S',512,64,8)]:
            for start in range(0,total,n):
                # Consecutive indices hit every code, and each high bit value
                # appears at every logical grid position within a block.
                with self.subTest(kind=kind,start=start):
                    data,expected=pack_logical(kind,list(range(start,start+n)),[0]*scales,[0]*32)
                    self.assert_bits(kind,data,expected)

    def test_all_sign_masks_and_scale_nibbles_in_every_group(self):
        for kind,total,n,nsc in [('IQ2_S',1024,32,16),('IQ3_S',512,64,8)]:
            for phase in range(256):
                indices=[(phase*17+i*43)%total for i in range(n)]
                scales=[(phase+i)%16 for i in range(nsc)]
                signs=[(phase+i*7)%256 for i in range(32)]
                data,expected=pack_logical(kind,indices,scales,signs,d=0.33325)
                self.assert_bits(kind,data,expected)

    def test_iq4_nonlinear_levels_in_both_planes(self):
        for phase in range(16):
            data,expected=pack_logical('IQ4_NL',[(phase+i*7)%16 for i in range(32)],[],[],d=-0.33325)
            self.assert_bits('IQ4_NL',data,expected)

    def test_literals(self):
        # First normative IQ2 grid is eight 8s: d=1, s=0 => each +1.
        data=bytearray(82);data[:2]=struct.pack('<e',1)
        self.assert_bits('IQ2_S',bytes(data),[1]*256)
        data[34]=0x81
        expected=[1]*256;expected[0]=expected[7]=-1
        self.assert_bits('IQ2_S',bytes(data),expected)
        # First IQ3_S grid is four 1s: scale nibble 2 -> multiplier 5.
        data=bytearray(110);data[:2]=struct.pack('<e',1);data[106:110]=b'\x22'*4
        self.assert_bits('IQ3_S',bytes(data),[5]*256)
        data=struct.pack('<e',1)+b'\xf0'*16
        self.assert_bits('IQ4_NL',data,[-127]*16+[113]*16)

    def test_f32_every_special_value_preserves_bits(self):
        patterns=[0,0x80000000,1,0x80000001,0x007fffff,0x00800000,
                  0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff,
                  0x7f800000,0xff800000,0x7fc00000,0xffc00001,
                  0x7f800001,0xff800001,0x7fffffff,0xffffffff]
        raw=b''.join(struct.pack('<I',p) for p in patterns)
        actual=dequantize('F32',raw,(len(patterns),))
        self.assertEqual(actual.device.type,'cpu')
        self.assertEqual([v&0xffffffff for v in actual.view(torch.int32).tolist()],patterns)

    def test_new_quant_signed_zero(self):
        for kind in ('IQ2_S','IQ3_S','IQ4_NL'):
            data,_=logical_fixture(kind)
            for bits in (b'\0\0',b'\0\x80'):
                # Logical fixture gives the sign of each nonzero value;
                # zero-scale multiplication must preserve it bit for bit.
                reference=dequant_block(kind,data)
                actual=dequant_block(kind,bits+data[2:])
                expected=torch.signbit(reference) ^ (bits==b'\0\x80')
                self.assertTrue(torch.equal(torch.signbit(actual),expected))

    def test_all_types_invalid_row_width_payload_and_shape(self):
        for kind,(block,size) in BY_NAME.items():
            invalid=[((),b''),((0,),b''),((-1,),b''),((block,),bytes(size+1)),
                     ((block,),bytes(size-1)),((2,block),bytes(size))]
            if block>1: invalid.append(((2,block//2),bytes(size)))
            for shape,payload in invalid:
                with self.subTest(kind=kind,shape=shape,length=len(payload)),self.assertRaises(ValueError):
                    dequantize(kind,payload,shape)


if __name__=='__main__':unittest.main()
