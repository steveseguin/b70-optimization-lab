"""Read-only final identity, receipt, proposal and bounded-build audit."""
import gzip,json,subprocess,sys,resource
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits,provenance,check_map
def main():
 limits();provenance()
 from startup_receipt97e import verify as startup_verify
 startup=startup_verify()
 from bundle_selection import aliases
 rows=[]
 for label in aliases():
  view=P/'selections'/label;seal=json.loads((view/'screen-seal.json').read_text())
  for key,root in [('sources',ROOT),('artifacts',view),('gates',view),('fixture_files',view)]:
   if key in seal:check_map(root,seal[key])
  rows.append(dict(view=label,seal_sha256=sha(view/'screen-seal.json')))
 from screen_jobs import verify
 verify()
 receipts=[]
 for f in (P/'build/startup97e/receipts').glob('*/*.json'):
  r=json.loads(f.read_text());assert r['passed'] and r['device_executed'] is False
  check_map(ROOT,r['sources']);assert r['fixture_sha256']==sha(P/'build/startup97e/fixture')
  receipts.append(dict(view=r['run']['view'],window=r['run']['window'],sha256=sha(f)))
 assert len(receipts)==startup['total_windows']
 assert len({(r['view'],r['window']) for r in receipts})==len(receipts)
 parent=P.parent/('packet105-head-split' if '105b' in P.name else 'packet106-draft-split')
 delta=[]
 for f in parent.rglob('*'):
  rel=f.relative_to(parent)
  if any(part in ('build','evidence','selections','oracle') for part in rel.parts):continue
  if f.is_file() and f.suffix in ('.cpp','.hpp','.inc'):
   target=P/rel;assert target.is_file()
   if sha(f)!=sha(target):delta.append(str(rel))
 assert delta==(['p105_runtime.hpp'] if '105b' in P.name else []),delta
 save(P/'evidence/runtime-delta.json',dict(passed=True,parent=str(parent.relative_to(ROOT)),changed_existing_runtime_files=delta,
      p105_runtime_sha256=sha(P/'p105_runtime.hpp'),request_reset_sha256=sha(P/'request_reset.hpp')))
 # All new files across both build trees, counted once per inode. Linked frozen
 # inputs are excluded; unchanged bytes remain individually hash-bound.
 seen=set();total=0;per_packet={}
 for name in ('packet105b-head-split','packet106b-draft-split'):
  count=0
  for f in (P.parent/name/'build').rglob('*'):
   if not f.is_file() or f.is_symlink():continue
   stat=f.stat();key=(stat.st_dev,stat.st_ino)
   if key not in seen:seen.add(key);count+=stat.st_size
  per_packet[name]=count;total+=count
 assert total<=250_000_000,total
 commands=[]
 for script in (['test_smoke12.py'] if '105b' in P.name else ['test_packet106.py','test_smoke12.py']):
  log=P/'evidence'/(script+'.final.log');cmd=[sys.executable,'-B',str(P/script)]
  with log.open('w') as stream:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=120)
  commands.append(dict(command=cmd,passed=True,source_sha256=sha(P/script),log_sha256=sha(log)))
 # Wrong/missing device qualification must refuse without constructing a device.
 from device_gate import require_micro
 try:require_micro()
 except FileNotFoundError:micro_pending=True
 else:micro_pending=False
 save(P/'evidence/final-verification.json',dict(passed=True,device_executed=False,views=rows,
      startup_windows=startup['total_windows'],completed_window_receipts=receipts,
      combined_new_build_bytes=total,per_packet_build_bytes=per_packet,
      runtime_delta=delta,tests=commands,micro_device_evidence_pending=micro_pending,
      peak_test_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print(json.dumps(dict(passed=True,windows=len(receipts),build_bytes=total,micro_device_evidence_pending=micro_pending)))
if __name__=='__main__':main()
