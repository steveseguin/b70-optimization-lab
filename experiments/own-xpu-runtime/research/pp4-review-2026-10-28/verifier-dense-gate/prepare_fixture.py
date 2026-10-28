#!/usr/bin/env python3
"""Future explicit extraction of ONE18MB tensor; never constructs/loads a model."""
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import stat

HERE=Path(__file__).resolve().parent
RUNTIME=HERE.parents[2]
def need(ok,why):
    if not ok:raise ValueError(why)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gguf',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    registration=json.loads((HERE/'registration.json').read_text())
    helper=RUNTIME/'research/dense-raw/cputest/gguf_dir.py'
    need(sha256(helper.read_bytes()).hexdigest()==registration['source_pins'][str(helper)],'directory reader source changed')
    spec=importlib.util.spec_from_file_location('verifier_gguf_dir',helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=a.gguf.resolve(strict=True);fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode),'regular GGUF source')
        rows=[r for r in module.directory(source) if r['name']=='blk.1.attn_qkv.weight'];need(len(rows)==1,'exact selected tensor in explicit shard')
        tensor=rows[0];need(tensor['type']==13 and tensor['dims']==[2560,10240] and tensor['bytes']==18022400,'registered Q5_K layout')
        need(0<=tensor['offset']<=before.st_size-tensor['bytes'],'bounded tensor source extent')
        raw=os.pread(fd,tensor['bytes'],tensor['offset']);need(len(raw)==tensor['bytes'],'complete tensor extraction')
        signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(signature(before)==signature(os.fstat(fd))==signature(os.stat(source)),'source changed during directory/extraction')
        inputs=(HERE/'inputs.f32').read_bytes();need(sha256(inputs).hexdigest()==registration['input_sha256'] and len(inputs)==30720,'pinned retained input rows')
        a.out.mkdir(parents=False,exist_ok=False)
        (a.out/'weights.q5k').write_bytes(raw);(a.out/'inputs.f32').write_bytes(inputs)
        receipt=dict(schema='verifier-dense-single-tensor-fixture-v1',tensor=tensor,source=dict(path=str(source),device=before.st_dev,inode=before.st_ino,bytes=before.st_size,mtime_ns=before.st_mtime_ns,ctime_ns=before.st_ctime_ns),
            weights_sha256=sha256(raw).hexdigest(),inputs_sha256=sha256(inputs).hexdigest(),registration_sha256=sha256((HERE/'registration.json').read_bytes()).hexdigest(),
            scope='Parsed exact tensor from supplied stable GGUF; full-file model hash not recomputed. No model graph/weights except selected18MB tensor loaded. Retained router activations are arbitrary matvec vectors, not selected QKV site inputs.')
        (a.out/'fixture.json').write_text(json.dumps(receipt,indent=2)+'\n')
    finally:os.close(fd)
if __name__=='__main__':main()
