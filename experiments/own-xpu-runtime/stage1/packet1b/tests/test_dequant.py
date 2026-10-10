"""Synthetic encoders are tests only: pack representable logical values, decode.

They are not weight quantizers. Vary every subblock, plane, index and sign;
expected values come from logical input arrays rather than reading packed bytes.
"""
import struct
import unittest
import torch
from loaders.dequant import dequant_block,dequantize,GRID,IQ4,BY_NAME


def pack_fixture(kind):
    count,size=BY_NAME[kind]
    b=bytearray(size)
    expected=[]
    d=0.125
    if kind=='F32':
        return struct.pack('<f',-1.5),[-1.5]
    if kind in ('IQ2_S','IQ3_S','IQ4_NL'):
        from test_ud_dequant import logical_fixture
        return logical_fixture(kind)
    if kind in ('F16','BF16'):
        value=-1.5
        return (struct.pack('<e',value) if kind=='F16' else struct.pack('<f',value)[2:]),[value]
    if kind=='Q8_0':
        b[:2]=struct.pack('<e',d)
        q=[i*8-128 for i in range(32)]
        b[2:]=struct.pack('<32b',*q)
        return bytes(b),[d*v for v in q]
    if kind=='Q3_K':
        b[-2:]=struct.pack('<e',d)
        scales=[(g*13)%64-32 for g in range(16)]
        for g,s in enumerate(scales):
            code=s+32
            b[96+g%8]|=(code&15)<<(4*(g//8))
            b[104+g%4]|=(code>>4)<<(2*(g//4))
        for slab in range(2):
            for plane in range(4):
                for lane in range(32):
                    i=slab*128+plane*32+lane
                    q=(i*3+i//8)%8-4
                    b[32+slab*32+lane]|=(q&3)<<(2*plane)
                    b[lane]|=int(q>=0)<<(slab*4+plane)
                    expected.append(d*scales[i//16]*q)
    elif kind in ('Q4_K','Q5_K'):
        b[:4]=struct.pack('<ee',d,0.0625)
        scales=[(7+g*9)%64 for g in range(8)]
        mins=[(61-g*11)%64 for g in range(8)]
        for g in range(4):
            b[4+g]=scales[g]|((scales[g+4]>>4)<<6)
            b[8+g]=mins[g]|((mins[g+4]>>4)<<6)
            b[12+g]=(scales[g+4]&15)|((mins[g+4]&15)<<4)
        start=16 if kind=='Q4_K' else 48
        for g in range(8):
            for lane in range(32):
                i=g*32+lane
                q=(lane*7+g*3)%(16 if kind=='Q4_K' else 32)
                b[start+(g//2)*32+lane]|=(q&15)<<(4*(g%2))
                if kind=='Q5_K': b[16+lane]|=(q>>4)<<g
                expected.append(d*scales[g]*q-0.0625*mins[g])
    elif kind=='Q6_K':
        b[-2:]=struct.pack('<e',d)
        scales=[g*17-128 for g in range(16)]
        b[192:208]=struct.pack('<16b',*scales)
        for slab in range(2):
            for plane in range(4):
                for lane in range(32):
                    i=slab*128+plane*32+lane
                    q=(i*7+i//8)%64-32
                    b[slab*64+(plane%2)*32+lane]|=((q+32)&15)<<(4*(plane//2))
                    b[128+slab*32+lane]|=((q+32)>>4)<<(2*plane)
                    expected.append(d*scales[i//16]*q)
    elif kind=='IQ4_XS':
        b[:2]=struct.pack('<e',d)
        high=0
        for g in range(8):
            scale=(g*11)%64-32
            b[4+g//2]|=((scale+32)&15)<<(4*(g%2))
            high|=((scale+32)>>4)<<(2*g)
            for lane in range(32):
                code=(lane+g*3)%16
                b[8+16*g+lane%16]|=code<<(4*(lane//16))
                expected.append(d*scale*IQ4[code])
        b[2:4]=struct.pack('<H',high)
    else:
        b[:2]=struct.pack('<e',d)
        for g in range(8):
            word=(g*2)<<28
            masks=[]
            for octet in range(4):
                sign=(g*17+octet*31)%128
                word|=sign<<(octet*7)
                masks.append(sign|((sign.bit_count()%2)<<7))
            b[66+g*4:70+g*4]=struct.pack('<I',word)
            for quad in range(8):
                index=(g*32+quad*5)%256
                b[2+8*g+quad]=index
                vals=GRID[index].to_bytes(4,'little')
                for component,value in enumerate(vals):
                    lane=4*quad+component
                    sign=-1 if masks[lane//8]&(1<<(lane%8)) else 1
                    expected.append(d*(0.5+g*2)*0.5*value*sign)
    return bytes(b),expected


class Dequant(unittest.TestCase):
    def test_literal_q3_negative_high_mask(self):
        b=bytearray(110); b[96:104]=bytes([0x11]*8); b[104:108]=bytes([0xaa]*4); b[-2:]=struct.pack('<e',1)
        # Each scale code=33 -> +1; low bits zero, absent high bits -> -4.
        self.assertTrue(torch.equal(dequant_block('Q3_K',bytes(b)),torch.full((256,),-4.)))

    def test_literal_q4_minimum(self):
        b=bytearray(144); b[:4]=struct.pack('<ee',2,3); b[8:12]=bytes([1]*4)
        out=dequant_block('Q4_K',bytes(b))
        self.assertTrue(torch.equal(out[:128],torch.full((128,),-3.)))
        self.assertTrue(torch.equal(out[128:],torch.zeros(128)))

    def test_literal_iq3_even_parity(self):
        b=bytearray(98); b[:2]=struct.pack('<e',1)
        # grid index zero is [4,4,4,4], scale=1/4, sign code 1 flips 0 and 7.
        b[66:70]=struct.pack('<I',1)
        out=dequant_block('IQ3_XXS',bytes(b))
        self.assertEqual(out[:8].tolist(),[-1,1,1,1,1,1,1,-1])

    def test_iq3_entire_codebook_and_sign_space(self):
        for start in range(0,256,64):
            b=bytearray(98); b[:2]=struct.pack('<e',4)
            b[2:66]=bytes(range(start,start+64))
            out=dequant_block('IQ3_XXS',bytes(b))
            expected=[v for word in GRID[start:start+64] for v in word.to_bytes(4,'little')]
            self.assertEqual(out.tolist(),expected)
        for sign in range(128):
            b=bytearray(98); b[:2]=struct.pack('<e',1); b[66:70]=struct.pack('<I',sign)
            out=dequant_block('IQ3_XXS',bytes(b))[:8]
            self.assertEqual(sum(v<0 for v in out),sign.bit_count()+sign.bit_count()%2)

    def test_signed_zero_float_formats(self):
        for kind in ('F16','BF16'):
            self.assertTrue(torch.signbit(dequant_block(kind,b'\0\x80')).item())

    def test_unknown_and_shape_reject(self):
        with self.assertRaises(ValueError): dequant_block('UNKNOWN',bytes(4))
        with self.assertRaises(ValueError): dequantize('Q8_0',bytes(34),(2,16))


def roundtrip_case(kind):
    def test(self):
        data,values=pack_fixture(kind)
        actual=dequant_block(kind,data)
        expected=torch.tensor(values,dtype=torch.float32)
        self.assertTrue(torch.equal(actual,expected),kind)
        self.assertTrue(torch.equal(actual.view(torch.uint8),dequant_block(kind,data).view(torch.uint8)))
        count,size=BY_NAME[kind]
        doubled=dequantize(kind,data+data,(2,count))
        self.assertTrue(torch.equal(doubled,expected.repeat(2,1)))
    return test


def bad_length_case(kind):
    def test(self):
        data,_=pack_fixture(kind)
        for b in (data[:-1],data+b'\0'):
            with self.assertRaises(ValueError): dequant_block(kind,b)
    return test


for kind in BY_NAME:
    setattr(Dequant,'test_representable_roundtrip_'+kind,roundtrip_case(kind))
    setattr(Dequant,'test_wrong_length_'+kind,bad_length_case(kind))
