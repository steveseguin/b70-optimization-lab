"""Independent CPU format oracle. No device runtime; torch tensors are CPU only."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import random
import struct
import sys
HERE=Path(__file__).resolve().parent
KINDS={'Q8_0':(8,32,34,32,2),'Q3_K':(11,256,110,16,14),'Q6_K':(14,256,210,16,18),
       'IQ3_XXS':(18,256,98,32,10),'IQ4_NL':(20,32,18,32,2),'IQ3_S':(21,256,110,32,6),
       'IQ2_S':(22,256,82,16,10),'IQ4_XS':(23,256,136,32,8)}
RAW={'F32':4,'F16':2,'BF16':2}
def row_bytes(kind,k):
    if kind in RAW:return RAW[kind]*k
    _,block,_,group,meta=KINDS[kind]
    if not k or k%block:raise ValueError('whole blocks per row')
    return (k//2 if kind=='Q3_K' else k)+4*k//group+k//block*meta

@lru_cache(maxsize=1)
def oracle():
    sys.path.insert(0,str(HERE.parents[1]/'stage1/packet1b'))
    from loaders import dequant
    return dequant

def scale(kind,b,i):
    d=oracle(); at=208 if kind=='Q6_K' else 108 if kind=='Q3_K' else 0
    f=d._f16(b,at);r=d._f32
    if kind=='IQ2_S':return r(r(f*(.5+((b[74+i//32]>>(4*((i//16)%2)))&15)))*.25)
    if kind=='IQ3_S':return r(f*(1+2*((b[106+i//64]>>(4*((i//32)%2)))&15)))
    if kind=='IQ3_XXS':return r(r(f*(.5+(int.from_bytes(b[66+4*(i//32):70+4*(i//32)],'little')>>28)))*.5)
    if kind=='Q6_K':return r(f*struct.unpack_from('b',b,192+i//16)[0])
    if kind=='Q3_K':
        g=i//16;s=((b[96+g%8]>>(4*(g//8)))&15)|(((b[104+g%4]>>(2*(g//4)))&3)<<4)
        return r(f*(s-32))
    if kind=='IQ4_XS':
        g=i//32;s=((b[4+g//2]>>(4*(g%2)))&15)|(((int.from_bytes(b[2:4],'little')>>(2*g))&3)<<4)
        return r(f*(s-32))
    return f

def expand(kind,packed,k):
    d=oracle()
    if kind in RAW:return bytes(packed)
    _,block,size,group,_=KINDS[kind];src_rb=k//block*size
    if not packed or len(packed)%src_rb:raise ValueError('whole source rows required')
    out=bytearray()
    for row in range(len(packed)//src_rb):
        codes=[];scales=bytearray();metadata=bytearray()
        for off in range(row*src_rb,(row+1)*src_rb,size):
            b=packed[off:off+size];unit=bytearray(b);at=208 if kind=='Q6_K' else 108 if kind=='Q3_K' else 0
            unit[at:at+2]=struct.pack('<e',1)
            # dequant.py is normative: decode with unit block scale, divide out
            # finite subscale to recover exact integer code. Zero subscales need
            # their source code reconstructed with a nonzero synthetic scale.
            if kind=='Q6_K':unit[192:208]=bytes([1])*16
            if kind=='Q3_K':unit[96:104]=bytes([0x11])*8;unit[104:108]=bytes([0xaa])*4 # signed scale +1
            if kind=='IQ4_XS':unit[2:4]=bytes([0xaa])*2;unit[4:8]=bytes([0x11])*4
            vals=d.dequant_block(kind,unit).tolist()
            codes.extend(int(round(v/scale(kind,unit,i))) for i,v in enumerate(vals))
            for i in range(0,block,group):scales+=struct.pack('<f',scale(kind,b,i))
            metadata+=b[at:at+2]
            if kind=='IQ2_S':metadata+=b[74:82]
            elif kind=='IQ3_S':metadata+=b[106:110]
            elif kind=='Q6_K':metadata+=b[192:208]
            elif kind=='Q3_K':metadata+=b[96:108]
            elif kind=='IQ4_XS':metadata+=b[2:8]
            elif kind=='IQ3_XXS':metadata+=bytes(int.from_bytes(b[66+g*4:70+g*4],'little')>>28 for g in range(8))
        q=bytes((codes[i]&15)|((codes[i+1]&15)<<4) for i in range(0,k,2)) if kind=='Q3_K' else bytes(c&255 for c in codes)
        out+=q+scales+metadata
    return bytes(out)

def prepare_cases(directory):
    d=oracle();rng=random.Random(5102026);directory.mkdir()
    hashes={};counts=0
    # Exhaustive grid coverage plus all scale nibbles, sign bytes and special
    # half scales. Rows are small independent fixtures, never large model reads.
    for kind,(tid,block,size,group,meta) in KINDS.items():
        raw=bytearray()
        for trial in range(64):
            b=bytearray(rng.randbytes(size));h=[0,0x8000,1,0x8001,0x3c00,0xbc00,0x7bff,0xfbff,0x7c00,0xfc00,0x7e00,0xfe00][trial%12]
            at=208 if kind=='Q6_K' else 108 if kind=='Q3_K' else 0;b[at:at+2]=struct.pack('<H',h)
            if kind=='IQ2_S':
                for q in range(32):
                    ix=(trial*32+q)%1024;b[2+q]=ix&255;b[66+q//4]=(b[66+q//4]&~(3<<(2*(q%4))))|((ix>>8)<<(2*(q%4)))
            if kind=='IQ3_S':
                for q in range(64):
                    ix=(trial*64+q)%512;b[2+q]=ix&255;b[66+q//8]=(b[66+q//8]&~(1<<(q%8)))|((ix>>8)<<(q%8))
            if kind=='IQ3_XXS':
                for q in range(64):b[2+q]=(trial*64+q)%256
            raw+=b
        ex=expand(kind,raw,block)
        expected=b''.join(d.dequant_block(kind,raw[i:i+size]).numpy().tobytes() for i in range(0,len(raw),size))
        path=directory/(kind+'.case');path.write_bytes(struct.pack('<6I',tid,block,64,len(raw),len(ex),len(expected))+raw+ex+expected)
        hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest();counts+=64*block
    return hashes
