#!/usr/bin/env python3
"""CPU-only admission/tokenization. Existing admitted shards, bounded headers only."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
LANE=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70'
sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/stage1/packet1b'))
from loaders.headers import gguf_header
sys.path.insert(0,str(LANE/'packet2-cpu-oracle'))
from tokenizer import Tokenizer

def prepare(out,prompt=None):
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True)
    out.mkdir(parents=True,exist_ok=False)
    admission=json.loads((LANE/'packet1/admission-receipt.json').read_text())
    assert admission['passed']
    identity=[]
    for item in admission['files']:
        p=Path(admission['model_dir'])/Path(item['path']).name
        s=p.stat();sig=dict(bytes=s.st_size,ctime_ns=s.st_ctime_ns,device=s.st_dev,inode=s.st_ino,mtime_ns=s.st_mtime_ns)
        assert sig==item['after'],f'admitted file changed: {p}'
        identity.append(f'{p.name} {s.st_size} {s.st_dev} {s.st_ino} {s.st_mtime_ns} {s.st_ctime_ns}')
    (out/'identity.tsv').write_text('\n'.join(identity)+'\n')
    census=json.loads((LANE/'packet1/tensor-census.json').read_text())['tensors'];rows=[]
    for t in census:
        layer=t['layer'] if t['layer'] is not None else -1
        mask=0 if t['component'] in ('embedding','ple_lookup') else 3 if t['hc_projection_replicated'] else 1 if 0<=layer<24 else 2
        rows.append(' '.join(map(str,[Path(t['shard']).name,t['name'],t['component'],t['type_id'],t['data_offset'],t['bytes'],layer,mask,len(t['dimensions']),*t['dimensions']])))
    (out/'plan.tsv').write_text('\n'.join(rows)+'\n')
    p=Path(admission['model_dir'])/Path(admission['files'][0]['path']).name
    with p.open('rb') as f: header=gguf_header(f,p.stat().st_size)
    with p.open('rb') as f: raw=f.read(header['header_bytes_read'])
    assert hashlib.sha256(raw).hexdigest()==admission['files'][0]['header_sha256']
    tok=Tokenizer(header['metadata'])
    prompt=prompt or LANE/'packet2-cpu-oracle/prompts/incident-retrospective.txt'
    text=prompt.read_text();ids=tok.encode(text);assert tok.decode(ids)==text
    (out/'tokens.txt').write_text(' '.join(map(str,ids))+'\n')
    with (out/'vocab.bin').open('wb') as f:
        for token in tok.tokens:
            b=token.encode() if token in tok.special else bytes(tok.dec[c] for c in token)
            f.write(struct.pack('<I',len(b)));f.write(b)
    receipt=dict(schema='own-runtime.iq3.packet4.input.v1',model_dir=admission['model_dir'],prompt=str(prompt),tokens=ids,prompt_sha256=hashlib.sha256(text.encode()).hexdigest(),header_bytes_read=2*len(raw),header_sha256=hashlib.sha256(raw).hexdigest(),tokenizer_source_sha256=hashlib.sha256((LANE/'packet2-cpu-oracle/tokenizer.py').read_bytes()).hexdigest(),files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()})
    (out/'input.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--prompt',type=Path);a=p.parse_args();prepare(a.output,a.prompt)
