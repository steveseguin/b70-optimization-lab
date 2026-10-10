#!/usr/bin/env python3
"""Read retained evidence only; neither Docker nor model/runtime imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PREFIX='patches/qwen38-flash-next-fp8-b70/'
SERIES=['vllm-lossless-mtp1-1b2a17c1','vllm-placement-mtp1-005dc578',
        'vllm-hctriton-mtp1-62219122','vllm-qsafused-mtp1-6d872457',
        'xpu-kernels-gdn-exact-serial-bbae3c5']

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def audit():
    record='repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/'
    reopen='experiments/qwen38-flash-next-fp8-b70/reopen-20261008/'
    identity=json.loads((ROOT/record/'identity.json').read_text())
    image=json.loads((ROOT/reopen/'image-plan.json').read_text())
    overlay=json.loads((ROOT/reopen/'overlay-manifest.json').read_text())
    files=[record+'identity.json',record+'README.md',record+'frozen-a367-packet.sha256',
           reopen+'image-plan.json',reopen+'overlay-manifest.json',
           identity['runtime']['kernel_stage_manifest'],
           'experiments/own-xpu-runtime/stage2/packet1/evidence/runtime-versions.txt']
    seals=[]
    for name in SERIES:
        manifest=ROOT/PREFIX/name/'series.sha256'
        files.append(str(manifest.relative_to(ROOT)))
        rows=[]
        for line in manifest.read_text().splitlines():
            if not line.strip() or line.startswith('#'):continue
            expected,relative=line.split(maxsplit=1);relative=relative.lstrip('*')
            target=manifest.parent/relative
            found=sha(target) if target.is_file() else None
            rows.append({'path':str(target.relative_to(ROOT)),'sha256':expected,
                         'observed_sha256':found,'matched':found==expected})
        seals.append({'series':name,'members':rows})
    return {'schema':'own-xpu-runtime.packet4.comparator-audit.v1',
        'a367': {'certified_image_digest':None, 'environment':'host Python 3.12 venv, torch 2.11.0+xpu, Triton 3.7.0, oneAPI 2025.3',
                 'record':identity['record'],'runtime':identity['runtime'],'configuration':identity['configuration'],
                 'sealed_series':seals},
        'reopen':{'image':image['image'],'overlay_manifest_sha256':sha(ROOT/reopen/'overlay-manifest.json'),
                  'upstream':overlay['upstream'],'head':overlay['head'],
                  'certified_as_A367':False,'generation_qualified':False},
        'native_extraction_ready':False,
        'blockers':['A367 is not a digest-pinned container; the guide explicitly calls its container route unbuilt/unadapted.',
                    'No reviewed source-bound native operator/state ABI adapter is present in this packet.',
                    'Eager full-token neutrality versus the graph-enabled certified line is not established.',
                    'Natural A367 MTP1 does not guarantee M=6; do not change its dispatch or invent rows.',
                    'Reopen full-model memory/output/teardown qualification and current host halt remain separate gates.'],
        'evidence':{f:sha(ROOT/f) for f in files}}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':
        p.error('requires nice 19 and OMP_NUM_THREADS=2')
    data=json.dumps(audit(),indent=2)+'\n'
    if a.output:a.output.write_text(data)
    else:print(data,end='')
