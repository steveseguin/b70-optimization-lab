"""Copy frozen packet70 source; no parent or shared screen edits."""
from pathlib import Path
import hashlib,json,shutil
P=Path(__file__).resolve().parent;ROOT=P.parents[3];BASE=P.parent/'packet70-record-bundle'
assert not (P/'main.cpp').exists()
pins={}
for f in BASE.iterdir():
 if f.is_file() and (f.suffix in ('.cpp','.hpp','.inc') or f.name in ('math_gate.py','kernel_gate.py','kernel_overlay.py','submission_overlay.py','rope.bf16','mtp-manifest.tsv','dispatch-speed6.json','memory-plan.json','selection.json')):
  shutil.copyfile(f,P/f.name);pins[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
for n in ('p28','prototype'):shutil.copytree(BASE/n,P/n,ignore=shutil.ignore_patterns('__pycache__'))
(P/'parent-source-manifest.json').write_text(json.dumps(pins,indent=2)+'\n')
(P/'build').mkdir(exist_ok=True)
