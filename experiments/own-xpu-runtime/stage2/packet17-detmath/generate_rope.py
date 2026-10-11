"""Pinned host authority: glibc powf/sinf/cosf, FP32 angle, BF16 ties-even.
Only regeneration uses libm. Frozen rope.bf16 bytes, not platform libm, define v2.
"""
import ctypes, hashlib, json, platform, struct
from pathlib import Path
P=Path(__file__).resolve().parent
M=ctypes.CDLL('libm.so.6')
for name in ('powf','sinf','cosf'):
 f=getattr(M,name);f.restype=ctypes.c_float;f.argtypes=[ctypes.c_float]*(2 if name=='powf' else 1)
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def bf(x):
 u=struct.unpack('<I',struct.pack('<f',x))[0];return (u+0x7fff+((u>>16)&1))>>16
values=[]
for pos in range(4096):
 for j in range(32):
  angle=f32(f32(pos)*M.powf(1e7,f32(-f32(2*j)/64.)))
  values.extend((bf(M.cosf(angle)),bf(M.sinf(angle))))
raw=struct.pack('<'+'H'*len(values),*values)
target=P/'rope.bf16'
if target.exists() and target.read_bytes()!=raw:raise SystemExit('pinned RoPE authority differs: refuse overwrite')
target.write_bytes(raw)
(P/'build').mkdir(exist_ok=True)
(P/'build/rope_table.hpp').write_text('#pragma once\nnamespace rope_constants {\ninline constexpr int positions=4096;\ninline constexpr uint16_t table[]={\n'+',\n'.join(','.join(str(v) for v in values[i:i+32]) for i in range(0,len(values),32))+'\n};\n}\n')
receipt=dict(schema='packet17.rope.v1',positions=4096,rotary=64,layout='little-endian uint16 BF16 [position][frequency][cos,sin]',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),authority='glibc scalar powf/cosf/sinf; f32(position * powf(1e7f,-2*j/64)); BF16 ties-even',libc=platform.libc_ver(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),libm_sha256=hashlib.sha256(Path('/lib/x86_64-linux-gnu/libm.so.6').read_bytes()).hexdigest(),device_executed=False)
(P/'rope-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
