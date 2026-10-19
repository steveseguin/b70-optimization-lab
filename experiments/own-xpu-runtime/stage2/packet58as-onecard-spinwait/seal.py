"""Seal the chain without modifying the completed bracket or rebuilding native code."""
import hashlib,json,os,resource,sys,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];Q=P/'screen';H=P/'lineage/packet58asc-before'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,r):p.write_text(json.dumps(r,indent=2)+'\n')
def verify(root,files):
 for n,h in files.items():assert sha(root/n)==h,n

def screen_verify():
 row=read(Q/'build-receipt.json')
 for n,h in row['sources'].items():
  path=ROOT/n
  if path.parent==P and (H/path.name).is_file():path=H/path.name
  assert sha(path)==h,n
 for key in ('artifacts','gates'):verify(Q,row[key])
 return row

def main():
 resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
 old=screen_verify()
 if '--verify' in sys.argv:
  row=read(P/'build-receipt.json')
  for root,key in ((ROOT,'sources'),(P,'artifacts'),(P,'gates')):verify(root,row[key])
  pins=read(P/'submission-pins.json');verify(ROOT,pins['sources'])
  assert pins['build_receipt_sha256']==sha(P/'build-receipt.json')
  print('PASS chain seal and unchanged historical screen seal');return
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert not (P/'READY-FOR-DEVICE.json').exists() and not (P/'evidence/card0-58as-a').exists()
 gates={}
 for n in ('k1-cpu.json','evidence/cpu-exactness.json','evidence/preparation.json','evidence/flags.json','evidence/analyzer-real-parent.json','evidence/fullshape-submit-cpu.json','evidence/postload-allocation-cpu.json'):
  g=read(P/n);assert g['passed'] and not g['device_executed'];gates[n]=sha(P/n)
 excluded={'build-receipt.json','submission-pins.json','ready.json','READY-FOR-DEVICE.json'}
 sources={}
 for f in P.glob('*'):
  if f.is_file() and f.suffix in ('.py','.json','.md','.snapshot') and f.name not in excluded:sources[str(f.relative_to(ROOT))]=sha(f)
 # Preserve original screen closure, substituting the exact historical bytes
 # only for root files deliberately changed for the chain.
 for n,h in old['sources'].items():
  f=ROOT/n
  if f.parent==P and (H/f.name).is_file():f=H/f.name
  sources[str(f.relative_to(ROOT))]=h
 sources[str((Q/'build-receipt.json').relative_to(ROOT))]=sha(Q/'build-receipt.json')
 for n in ('evidence/chain-native-interface.json','evidence/postload-census.json','evidence/58c-kd/run/progress.jsonl'):sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 # Current chain files take precedence over their saved historical counterparts.
 verify(ROOT,sources)
 from shared_oracle import completed_binding
 from composition import DIMENSIONS
 row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=old['artifacts'],gates=gates,arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',kv_dtype='BF16',hc='p60fusion',**DIMENSIONS,lookups='resident',wait_policy='spin',wait_seconds=300,cache_maintenance='overlap',cache_cap='max',cache_allocation_bytes=21552729600,oracle=completed_binding(),native_recompiled=False,runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip())
 save(P/'build-receipt.json',row)
 names=('packet58_submission.py','composition.py','submission_cli.py','shared_submission_cli.py','suite_metrics.py','submission-policy.json','record-threshold.snapshot')
 save(P/'submission-pins.json',dict(schema='packet58as.submission-pins.v1',build_receipt_sha256=sha(P/'build-receipt.json'),sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in names},artifacts=old['artifacts'],finalized_before_chain=True))
 print('PASS minimal chain seal; native and historical screen bytes preserved')
if __name__=='__main__':main()
