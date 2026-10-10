"""Original scalar-index GGUF decoders; format data, not ggml kernels, reused.

See FORMAT.md for independent byte equations and provenance. Each decoder
returns FP32 CPU values in the file's element order. F16 scales become exact
FP32; round after scale multiplication, then quant multiplication, then offset
subtraction (no FMA). There is no quantizer or claim of losslessness to FP8.
"""
import json
import struct
from pathlib import Path
import torch
from .headers import TYPES

GRID = json.loads(Path(__file__).with_name('iq3-grid.json').read_text())['packed_u32_le']
IQ4 = (-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113)
BY_NAME = {v[0]:v[1:] for v in TYPES.values()}


def _f16(b,at=0):
    """Read little-endian binary16 and exactly widen it to Python float."""
    return struct.unpack_from('<e',b,at)[0]


def _f32(x):
    """Explicit IEEE binary32 round-to-nearest-even; no fused operations."""
    return struct.unpack('<f',struct.pack('<f',x))[0]


def dequant_block(kind, data):
    """Decode exactly one block using FORMAT.md's scalar element equations.

    Scale multiplication and subsequent products/subtraction each round FP32.
    IQ3: sign parity is reconstructed, grid is normative format data. F16 and
    BF16 preserve signed zeros; NaNs are allowed format values (not logits).
    """
    if kind not in BY_NAME:
        raise ValueError('unsupported quantization')
    count,size = BY_NAME[kind]
    if len(data)!=size:
        raise ValueError('wrong block byte length')
    b = data
    if kind=='F16':
        return torch.tensor([_f16(b)],dtype=torch.float32,device='cpu')
    if kind=='BF16':
        return torch.tensor([struct.unpack('<f',b'\0\0'+b)[0]],dtype=torch.float32,device='cpu')
    result = []
    for i in range(count):
        if kind=='Q8_0':
            q = struct.unpack_from('<b',b,2+i)[0]
            value = _f32(_f16(b)*q)
        elif kind=='Q3_K':
            group = i//16
            sc = ((b[96+group%8] >> (4*(group//8))) & 15) | (((b[104+group%4] >> (2*(group//4))) & 3)<<4)
            low = (b[32+(i//128)*32+i%32] >> (2*((i%128)//32))) & 3
            high = (b[i%32] >> (i//32)) & 1
            q = low - 4*(1-high)
            value = _f32(_f32(_f16(b,108)*(sc-32))*q)
        elif kind in ('Q4_K','Q5_K'):
            group = i//32
            if group<4:
                sc,mn = b[4+group]&63,b[8+group]&63
            else:
                sc = (b[12+group-4]&15) | ((b[4+group-4]>>6)<<4)
                mn = (b[12+group-4]>>4) | ((b[8+group-4]>>6)<<4)
            qstart = 16 if kind=='Q4_K' else 48
            q = (b[qstart+(i//64)*32+i%32] >> (4*((i%64)//32))) & 15
            if kind=='Q5_K':
                q |= ((b[16+i%32] >> group)&1)<<4
            value = _f32(_f32(_f32(_f16(b)*sc)*q)-_f32(_f16(b,2)*mn))
        elif kind=='Q6_K':
            low = (b[(i//128)*64+i%64] >> (4*((i%128)//64))) & 15
            high = (b[128+(i//128)*32+i%32] >> (2*((i%128)//32))) & 3
            sc = struct.unpack_from('<b',b,192+i//16)[0]
            value = _f32(_f32(_f16(b,208)*sc)*((low|(high<<4))-32))
        elif kind=='IQ4_XS':
            group = i//32
            low_sc = (b[4+group//2] >> (4*(group%2))) & 15
            high_sc = (int.from_bytes(b[2:4],'little') >> (2*group)) & 3
            sc = (low_sc|(high_sc<<4))-32
            index = (b[8+group*16+i%16] >> (4*((i%32)//16))) & 15
            value = _f32(_f32(_f16(b)*sc)*IQ4[index])
        else:  # IQ3_XXS, eight groups of 32; two grid indices per eight.
            group,within = divmod(i,32)
            word = int.from_bytes(b[66+4*group:70+4*group],'little')
            sign_index = (word >> (7*(within//8))) & 127
            sign_mask = sign_index | ((sign_index.bit_count()%2)<<7)
            sign = -1 if (sign_mask>>(within%8))&1 else 1
            packed = GRID[b[2+i//4]]
            value_in_grid = (packed >> (8*(i%4))) & 255
            scale = _f32(_f32(_f16(b)*(0.5+(word>>28)))*0.5)
            value = _f32(_f32(scale*value_in_grid)*sign)
        result.append(value)
    return torch.tensor(result,dtype=torch.float32,device='cpu')


def dequantize(kind, data, shape):
    """Decode row-major shape; GGUF fastest-first dimensions must be reversed.

    Whole blocks per row only. No extra bytes tolerated. Output is CPU FP32.
    """
    from .headers import product
    count = product(list(shape))
    if kind not in BY_NAME:
        raise ValueError('unsupported quantization')
    block,size = BY_NAME[kind]
    if shape[-1]%block or len(data)!=count//block*size:
        raise ValueError('shape/payload mismatch')
    return torch.cat([dequant_block(kind,data[i:i+size]) for i in range(0,len(data),size)]).reshape(shape)
