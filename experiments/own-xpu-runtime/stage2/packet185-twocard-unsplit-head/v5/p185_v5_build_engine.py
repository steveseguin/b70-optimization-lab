"""Packet185: NO REBUILD. Reuse packet183's linked engines byte for byte.

Packet185 changes only the sealed selection (target head split -> full head on rank 1)
and the Python harness. The device engine is packet183's `v5/build/device/own-rt-iq3`
(sha 36e476d1...): the 78 packet136 parent objects linked unchanged plus packet183's
entry-main/p49d_submit/s1_submit. With `dense_scales: expanded` every S1 site issues the
production kernels (packet183 full-shape gate), so its `production` selection is bundle 8.

main() copies the two engines and packet183's three gnu-host objects that the CPU
fixtures link (entry-main.o, p49d_submit.o, s1_submit.o; device objects are not needed),
recreates the 78 `inherited/` links to the pinned packet103/136 objects
(`immutable-binaries.json`), and verifies every byte against packet183's committed build
receipt (`lineage-inputs/packet183-own/v5/evidence/build.json`) and the parent pins.
No compiler runs. Helpers (P, LOCAL, sha, save, limits, run, compiler_turn, ...) keep the
packet183 interface for the inherited CPU gates.
"""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;LOCAL=P.parent;ROOT=P.parents[4];STAGE=P.parents[1];BASE=LOCAL;B=P/'build'
CHECKED=LOCAL/'build/checked'/LOCAL.relative_to(ROOT)
SOURCE=STAGE/'packet183-twocard-s1-micro/v5/build'
RECEIPT=LOCAL/'lineage-inputs/packet183-own/v5/evidence/build.json'
OLD='experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/v5/build/'
FLOOR=25_000_000_000  # coordinator rule for this packet: keep df / >= 25 GB (packet184 builds concurrently)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,row):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=FLOOR,'root free below the 25 GB floor'
 size=sum(f.stat().st_size for f in LOCAL.rglob('*') if f.is_file() and not f.is_symlink() and 'build' in f.parts and not f.is_relative_to(P/'evidence'))
 assert size<=300_000_000,size
 return size
def compiler_turn():
 import sys
 if str(LOCAL) not in sys.path:sys.path.append(str(LOCAL))
 spec=importlib.util.spec_from_file_location('ops_compile_turn',STAGE.parent/'ops/compile_turn.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def run(cmd,name):
 limits();t=time.monotonic()
 with compiler_turn(),(B/(name+'.log')).open('w') as log:subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 print(name,'PASS',flush=True);return dict(name=name,command=list(map(str,cmd)),seconds=time.monotonic()-t)
COPIED={'device':('own-rt-iq3',),'gnu-host':('own-rt-iq3','entry-main.o','p49d_submit.o','s1_submit.o')}
def main():
 limits();(LOCAL/'build').mkdir(exist_ok=True)
 if not (LOCAL/'build/checked').exists():(LOCAL/'build/checked').symlink_to('../native-base',target_is_directory=True)
 receipt=json.loads(RECEIPT.read_text());assert receipt['passed'] and receipt['device_executed'] is False
 pinned=json.loads((LOCAL/'immutable-binaries.json').read_text())
 artifacts,copies,inherited={}, {}, {}
 for mode,names in COPIED.items():
  dest=B/mode;dest.mkdir(parents=True,exist_ok=True)
  for name in names:
   src=SOURCE/mode/name;target=dest/name
   if not target.exists():shutil.copy2(src,target)
   assert sha(target)==sha(src),'copy differs: '+name
   copies[str(target.relative_to(ROOT))]=dict(source=str(src.relative_to(ROOT)),sha256=sha(target))
   if name=='own-rt-iq3':
    expected=receipt['artifacts'][OLD+mode+'/own-rt-iq3']
    assert sha(target)==expected,'engine differs from packet183 build receipt: '+mode
    artifacts[str(target.relative_to(ROOT))]=expected
  (dest/'inherited').mkdir(exist_ok=True)
  for link in sorted((SOURCE/mode/'inherited').iterdir()):
   resolved=link.resolve();digest=pinned[str(resolved)]
   assert sha(resolved)==digest,'frozen parent object changed: '+str(resolved)
   mine=dest/'inherited'/link.name
   if not mine.is_symlink():mine.symlink_to(resolved)
   assert mine.resolve()==resolved and sha(mine)==digest
   inherited[str(resolved.relative_to(ROOT))]=digest
 parent_inputs={k:v for k,v in receipt['sources'].items() if 'packet183-twocard-s1-micro' not in k}
 assert all(inherited[k]==v for k,v in parent_inputs.items() if k in inherited)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [*[P/'native'/n for n in ('engine_bracket.hpp','draft_bracket.hpp','bracket_boundary.hpp','probe_exchange.hpp','split_timing.hpp')],*P.glob('native-src/*'),P/'p185_v5_build_engine.py',RECEIPT]}
 sources.update(inherited)
 save(P/'evidence/build.json',dict(passed=True,device_executed=False,rebuilt=False,compiler_runs=0,
  mode='reuse of packet183 linked engines (no compile, no relink)',
  binary_sha256=artifacts[str((B/'device/own-rt-iq3').relative_to(ROOT))],
  provenance=dict(receipt=str(RECEIPT.relative_to(ROOT)),receipt_sha256=sha(RECEIPT),
   note='packet183 compiled these engines from its v5/native-src at commit 1d595ab98; packet185 native-src is the identity-rewritten copy (include paths renamed only) kept for the CPU fixtures'),
  sources=sources,artifacts=artifacts,copies=copies,inherited_parent_objects=len(inherited),commands=[],
  max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,build_bytes=limits()))
 print('reuse PASS: device',artifacts[str((B/'device/own-rt-iq3').relative_to(ROOT))][:16],'parent objects',len(inherited))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
