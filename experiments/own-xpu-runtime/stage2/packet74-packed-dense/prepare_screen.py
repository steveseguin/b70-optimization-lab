"""Snapshot v4-lanes and prepare coordinator-only fixed quick jobs."""
from pathlib import Path
import hashlib,json,shutil
P=Path(__file__).resolve().parent;ROOT=P.parents[3];S=P/'screen'
SOURCE=P.parent/'screen/v4-lanes';Q=P.parent/'packet69-rank1-head/screen/quick'
assert SOURCE.is_dir() and not S.exists()
S.mkdir();pins={}
for src in SOURCE.iterdir():
 if src.is_file() and (src.suffix=='.py' or src.name in ('placements.json','placement-jobs.txt','reference.json','integration.patch','screen-integration.patch','wrapper-seal.json')):
  if src.name.startswith('test_') and src.name not in ('test_reporting.py','test_devices.py','test_lane_admission.py'):continue
  shutil.copyfile(src,S/src.name);pins[str(src.relative_to(ROOT))]=hashlib.sha256(src.read_bytes()).hexdigest()
for n in ('run.py','compare.py'):
 shutil.copyfile(Q/n,S/n);pins[str((Q/n).relative_to(ROOT))]=hashlib.sha256((Q/n).read_bytes()).hexdigest()
def edit(name,old,new):
 p=S/name;s=p.read_text();assert old in s,(name,old);p.write_text(s.replace(old,new))
edit('placement.py',"root.parent.parent.name == 'packet64-record-bundle'", "root.parent.parent.name in ('packet64-record-bundle','packet74-packed-dense')")
edit('screen.py',"WRITES =", "SHARED = HERE.parents[1] / 'screen'\n\nWRITES =")
edit('screen.py',"HERE.parent / 'v3'", "SHARED / 'v3'")
edit('screen.py',"HERE.parent / 'v2'", "SHARED / 'v2'")
edit('screen.py',"HERE.parent / ('fault-'", "SHARED / ('fault-'")
edit('test_reporting.py',"stack.enter_context(patch.object(s,'HERE',here))", "stack.enter_context(patch.object(s,'HERE',here))\n            stack.enter_context(patch.object(s,'SHARED',shared.parent))")
edit('run.py',"    require(args.authorized_device_window and args.fault_review", "    if args.lane == 'B':\n        from winner import verify_lane_a\n        verify_lane_a()\n    require(args.authorized_device_window and args.fault_review")
edit('compare.py',"sha(QUICK / 'wrapper-seal.json')", "sha(QUICK / 'placement-validation/wrapper-seal.json')")
for lane,order in {'A':('production','head-packed','dense-packed','combined','production'),'B':('production','head-packed','production')}.items():
 lines=['# out|lineage|seal|binary|dispatch|placement']
 for i,name in enumerate(order,1):
  v=P/'selections'/name
  lines.append('|'.join(map(str,(f'p74-quick-{lane}-{i}-{name}-a',v,v/'screen-seal.json',v/'build/device/own-rt-iq3',v/'dispatch-speed6.json','1'))))
 (S/f'jobs-{lane}.txt').write_text('\n'.join(lines)+'\n')
(S/'parent-wrapper.json').write_text(json.dumps(dict(source=str(SOURCE.relative_to(ROOT)),pins=pins),indent=2)+'\n')
print('private v4-lanes snapshot; A full grid, B conditional winner sandwich')
