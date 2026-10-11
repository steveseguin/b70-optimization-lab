#!/usr/bin/env python3
"""Bounded CPU runner; incremental native evidence, read-only admitted weights."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--build',type=Path,required=True);ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--seconds',type=int,default=9000);ap.add_argument('--tokens',type=int,default=64);a=ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    assert 0<a.seconds<=10800 and 1<=a.tokens<=64
    a.out.mkdir(parents=True,exist_ok=False)
    identity=json.loads((HERE/'arithmetic.json').read_text())
    for n,h in identity['arithmetic_sources'].items():assert sha(ROOT/n)==h,n
    inp=json.loads((a.input/'input.json').read_text())
    for n,h in inp['files'].items():assert sha(a.input/n)==h,n
    frozen=HERE.parent/'packet2-cpu-oracle/runs/official-sigmoid-20261011/incident-retrospective/input.json'
    assert inp['tokens']==json.loads(frozen.read_text())['tokens']
    assert inp['prompt_sha256']==sha(HERE.parent/'packet2-cpu-oracle/prompts/incident-retrospective.txt')
    proof=json.loads((HERE/'proof.json').read_text());assert proof['passed'] and proof['binary_sha256']==sha(a.build/'matmul.so')
    build=json.loads((HERE/'build-receipt.json').read_text())
    assert build['passed'] and sha(a.build/'oracle')==build['binaries']['oracle']
    for name,digest in build['sources'].items():assert sha(ROOT/name)==digest,name
    directory=a.out/'incident-retrospective'
    cmd=[str(a.build/'oracle'),str(a.input),str(directory),str(a.seconds),str(a.tokens)]
    receipt=dict(schema='iq3-runtime-cpu-oracle.run.v1',status='running',started_utc=datetime.now(timezone.utc).isoformat(),
        command=cmd,arithmetic=identity,device_executed=False,nice=19,OMP_NUM_THREADS=8,preparation_threads=2,
        address_space_cap_bytes=38_000_000_000,model=json.loads((HERE.parent/'packet1/admission-receipt.json').read_text()),
        prompt_tokens=len(inp['tokens']),requested_tokens=a.tokens,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.suffix in ('.cpp','.py')},
        binary_sha256=sha(a.build/'oracle'),proof_sha256=sha(HERE/'proof.json'),input_sha256=sha(a.input/'input.json'))
    save(a.out/'receipt.json',receipt);started=time.monotonic()
    with (a.out/'stdout.txt').open('w') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'IQ3_MODEL_DIR':inp['model_dir'],'OMP_NUM_THREADS':'8'})
        def forward(signum,frame):
            if child.poll() is None:child.send_signal(signum)
        for signum in (signal.SIGTERM,signal.SIGINT):signal.signal(signum,forward)
        receipt['pid']=child.pid;save(a.out/'receipt.json',receipt)
        code=child.wait()
    receipt.update(status='completed' if code==0 else 'failed-or-stopped',returncode=code,elapsed_seconds=time.monotonic()-started,completed_utc=datetime.now(timezone.utc).isoformat())
    save(a.out/'receipt.json',receipt)
    if (directory/'result.json').exists():
        shutil.copyfile(HERE/'arithmetic.json',directory/'arithmetic.json')
        result=json.loads((directory/'result.json').read_text())
        receipt['status']=result['status']
        vocab=[]
        with (a.input/'vocab.bin').open('rb') as f:
            while h:=f.read(4):vocab.append(f.read(struct.unpack('<I',h)[0]))
        result['text']=b''.join(vocab[i] for i in result['tokens']).decode('utf-8',errors='replace')
        result['prompt_tokens']=len(inp['tokens']);result['id']='incident-retrospective'
        save(directory/'result.json',result)
        # Save exact bytes of verbose site logs in a reproducible compressed form.
        receipt['compressed_logs']={}
        for name in ('progress.jsonl','timings.jsonl'):
            p=directory/name
            if p.exists():
                receipt['compressed_logs'][name]=dict(sha256=sha(p),bytes=p.stat().st_size)
                with p.open('rb') as src,(directory/(name+'.gz')).open('wb') as raw:
                    with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as dst:shutil.copyfileobj(src,dst)
                with gzip.open(directory/(name+'.gz'),'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha(p)
                p.unlink()
        receipt['coverage']=dict(prompts=1,input_tokens=len(inp['tokens']),generated_tokens=len(result['tokens']),
            step1_layers=len(list((directory/'step1').glob('layer-*.bf16'))),fixture_steps=len(list(directory.glob('step*'))))
        receipt['result_sha256']=sha(directory/'result.json')
    save(a.out/'receipt.json',receipt)
    print(json.dumps(receipt.get('coverage',{})),flush=True)
    raise SystemExit(code)
if __name__=='__main__':main()
