"""Seal the chain; the completed bracket's screen seal stays verifiable byte for byte.

packet58asd rebuilt own-rt-iq3 with a CLI --wait-policy option. The historical
screen seal is checked against lineage/packet58asd-before copies of the two
changed native sources and the bracket binary kept in build/bracket/.
"""
import hashlib,json,os,resource,sys,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];Q=P/'screen';H=P/'lineage/packet58asc-before'
H2=P/'lineage/packet58asd-before';CHANGED=('native/generated/main.cpp','native/bracket_table.hpp')
REBUILT={'build/device/own-rt-iq3':'build/bracket/device/own-rt-iq3'}
# Ignored intermediates recompiled by the one packet58asd turn; their bracket digests are
# recorded, and the retained bracket executables above are verified instead.
OBJECTS=tuple(f'build/{m}/entry-main.o' for m in ('device','gnu-host','intel-host'))
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
  elif path.is_relative_to(P) and str(path.relative_to(P)) in CHANGED:path=H2/path.relative_to(P)
  assert sha(path)==h,n
 for n,h in row['artifacts'].items():assert sha(P/n)==h,n
 assert sorted(r['object'] for r in row['superseded_bracket_objects'])==sorted(OBJECTS)
 verify(Q,row['gates'])
 return row

def main():
 resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
 old=screen_verify()
 if '--verify' in sys.argv:
  row=read(P/'build-receipt.json')
  for root,key in ((ROOT,'sources'),(P,'artifacts'),(P,'gates')):verify(root,row[key])
  pins=read(P/'submission-pins.json');verify(ROOT,pins['sources'])
  for r in row['bracket_native']:assert sha(ROOT/r['parent_relpath'])==r['parent_digest'],r['name']
  assert pins['build_receipt_sha256']==sha(P/'build-receipt.json')
  print('PASS chain seal and unchanged historical screen seal');return
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert not (P/'READY-FOR-DEVICE.json').exists() and not (P/'evidence/card0-58as-a').exists()
 gates={}
 for n in ('k1-cpu.json','evidence/cpu-exactness.json','evidence/preparation.json','evidence/flags.json','evidence/chain-cpu-exactness.json','evidence/chain-flags.json','evidence/analyzer-real-parent.json','evidence/fullshape-submit-cpu.json','evidence/postload-allocation-cpu.json','evidence/build.json','evidence/wait-policy.json','evidence/native-parser.json'):
  g=read(P/n);assert g['passed'] and not g['device_executed'];gates[n]=sha(P/n)
 excluded={'build-receipt.json','submission-pins.json','ready.json','READY-FOR-DEVICE.json'}
 sources={}
 for f in P.glob('*'):
  if f.is_file() and f.suffix in ('.py','.json','.md','.snapshot') and f.name not in excluded:sources[str(f.relative_to(ROOT))]=sha(f)
 superseded=[]
 # Preserve original screen closure, substituting the exact historical bytes
 # only for root files deliberately changed for the chain.
 for n,h in old['sources'].items():
  f=ROOT/n
  if f.parent==P and (H/f.name).is_file():f=H/f.name
  elif f.is_relative_to(P) and str(f.relative_to(P)) in CHANGED:f=H2/f.relative_to(P)
  sources[str(f.relative_to(ROOT))]=h
 for r in old.get('superseded_bracket_objects',[]):superseded.append(r);sources[str((P/r['object']).relative_to(ROOT))]=sha(P/r['object'])
 assert sorted(r['object'] for r in superseded)==sorted(OBJECTS)
 orig=read(H/'screen-build-receipt.json')['artifacts']
 sources[str((Q/'build-receipt.json').relative_to(ROOT))]=sha(Q/'build-receipt.json')
 for n in ('evidence/chain-native-interface.json','evidence/postload-census.json','evidence/58c-kd/run/progress.jsonl','chain-interface.patch',*CHANGED):sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 # Current chain files take precedence over their saved historical counterparts.
 verify(ROOT,sources)
 from shared_oracle import completed_binding
 from composition import DIMENSIONS
 row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts={n:sha(P/n) for n in orig},bracket_native=[dict(name=n,parent_relpath=str((P/b).relative_to(ROOT)),parent_digest=orig[n]) for n,b in REBUILT.items()],superseded_bracket_objects=superseded,chain_interface_patch=dict(name='chain-interface.patch',parent_relpath=str((P/'chain-interface.patch').relative_to(ROOT)),parent_digest=sha(P/'chain-interface.patch')),gates=gates,arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',kv_dtype='BF16',hc='p60fusion',**DIMENSIONS,lookups='resident',wait_policy='spin',wait_seconds=300,cache_maintenance='overlap',cache_cap='max',cache_allocation_bytes=21552729600,oracle=completed_binding(),native_recompiled=True,native_change='CLI --wait-policy poll|spin only (default poll); chain windows pass spin',revision='packet58asd',runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],stdin=subprocess.DEVNULL,text=True).strip())
 save(P/'build-receipt.json',row)
 names=('packet58_submission.py','composition.py','submission_cli.py','shared_submission_cli.py','suite_metrics.py','submission-policy.json','record-threshold.snapshot')
 save(P/'submission-pins.json',dict(schema='packet58as.submission-pins.v1',build_receipt_sha256=sha(P/'build-receipt.json'),sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in names},artifacts=row['artifacts'],finalized_before_chain=True))
 print('PASS minimal chain seal; rebuilt chain binary bound; historical screen bytes preserved')
if __name__=='__main__':main()
