#!/usr/bin/env python3
"""Optional, offline synthetic cross-check; never part of the runtime.

Uses upstream's independently implemented NumPy equations as a second oracle.
No source code is copied. All three imported blobs are pinned below; quants.py
matches the original e3546c7 source receipt, while helper blobs are from the
local 23b0202 source snapshot. Requires an explicit path to that local gguf
directory, never fetches dependencies, and never reads a model or device.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import types

SOURCES={
    'quants.py':'2c927a1b3d9f0920dcf4007fb686e1b0999333e9f65ce43dcc689900c0beae8b',
    'constants.py':'d314d34803a0b7ed8a4e4a24bceced938dfad6e404136ab38b6e1db2fe98f23b',
    'lazy.py':'dbc98e3ee9ef8606df34e9d91f98ab29c2697e6824995f1dd8952938c135ad85',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--receipt',type=Path)
    args=parser.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':
        raise SystemExit('Run nice 19 ionice -c 3 env OMP_NUM_THREADS=2')
    for name,digest in SOURCES.items():
        if hashlib.sha256((args.source_dir/name).read_bytes()).hexdigest()!=digest:
            raise SystemExit('unrecognized source hash: '+name)
    # Avoid package __init__, which imports unrelated writer/tokenizer code.
    package=types.ModuleType('offline_quant_research')
    package.__path__=[str(args.source_dir)]
    sys.modules[package.__name__]=package
    for name in ('constants','lazy','quants'):
        spec=importlib.util.spec_from_file_location(package.__name__+'.'+name,args.source_dir/(name+'.py'))
        module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=module
        spec.loader.exec_module(module)
    upstream=sys.modules[package.__name__+'.quants']
    import numpy as np
    import torch
    torch.set_num_threads(2)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from loaders.dequant import BY_NAME,dequantize
    rng=np.random.default_rng(20261010)
    rows=[]
    # Finite scales include positive/negative zero, smallest binary16
    # subnormal/normal, high finite magnitude, and inexact decimal values.
    scales=[0x0000,0x8000,0x0001,0x8001,0x03ff,0x0400,0x3555,0xb555,
            0x3c00,0xbc00,0x7bff,0xfbff]
    for kind in ('IQ2_S','IQ3_S','IQ4_NL'):
        count,size=BY_NAME[kind]
        blocks=rng.integers(0,256,(len(scales)*16,size),dtype=np.uint8)
        for i,block in enumerate(blocks):
            block[:2]=np.frombuffer(struct.pack('<H',scales[i%len(scales)]),dtype=np.uint8)
        external=upstream.dequantize(blocks,getattr(upstream.GGMLQuantizationType,kind))
        local=dequantize(kind,blocks.tobytes(),(len(blocks),count)).numpy()
        if not np.array_equal(external.view(np.uint32),local.view(np.uint32)):
            raise AssertionError(kind+' bit mismatch')
        rows.append({'type':kind,'blocks':len(blocks),'values':int(local.size),
                     'input_sha256':hashlib.sha256(blocks.tobytes()).hexdigest(),
                     'f32_le_sha256':hashlib.sha256(local.astype('<f4').tobytes()).hexdigest(),
                     'all_bits_equal':True})
    receipt={'schema':'own-xpu-runtime.ud-mixed-dequant.external-crosscheck.v1',
             'device':'cpu','weights':'none; deterministic synthetic blocks',
             'seed':20261010,'numpy':np.__version__,'torch':torch.__version__,
             'source_dir':str(args.source_dir),'source_sha256':SOURCES,
             'quants_source_receipt_revision':'e3546c7948e3af463d0b401e6421d5a4c2faf565',
             'helper_snapshot_revision':'23b0202a189c44a54625aadcb37a946dd1d6278d',
             'runtime_dependency':False,'passed':True,'checks':rows}
    if args.receipt:args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
