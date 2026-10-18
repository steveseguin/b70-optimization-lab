#!/usr/bin/env python3
"""Copy the frozen source packet, never its build or device windows."""
from pathlib import Path
import hashlib,json,shutil
P=Path(__file__).resolve().parent;BASE=P.parent/'packet64-record-bundle';ROOT=P.parents[3]
assert not (P/'p67_hc.hpp').exists(),'historical creation helper; never overwrite the finished packet'
pins={}
for p in BASE.iterdir():
    if p.is_file() and (p.suffix in ('.cpp','.hpp') or p.name in ('math_gate.py','kernel_gate.py','kernel_overlay.py','submission_overlay.py','rope.bf16','mtp-manifest.tsv','dispatch-speed6.json','memory-plan.json','selection.json')):
        shutil.copyfile(p,P/p.name);pins[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
for name in ('p28','prototype'):
    shutil.copytree(BASE/name,P/name,ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
(P/'parent-source-manifest.json').write_text(json.dumps(pins,indent=2)+'\n')
for name in ('build','evidence'):(P/name).mkdir(exist_ok=True)
# Wrapper is an independent copy; no existing seal or output is imported.
src=P.parent/'packet65-expert-occupancy'
for folder in ('screen','screen/quick'):
    dest=P/folder;dest.mkdir(exist_ok=True)
    for p in (src/folder).iterdir():
        if p.is_file() and (p.suffix=='.py' or p.name in ('placements.json','placement-jobs.txt','wrapper-seal.json')):
            shutil.copyfile(p,dest/p.name)
for name in ('build_engine.py','cpu_fixture.py'):
    shutil.copyfile(src/name,P/name)
print('copied frozen source only')
