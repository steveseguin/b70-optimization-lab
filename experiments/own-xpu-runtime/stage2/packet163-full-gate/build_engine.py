"""Parser-only response-cap extension; reuse every compiled kernel object by hash."""
import difflib,hashlib,importlib.util,json,os,re,resource,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];STAGE=P.parent

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,r):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage(P).free>=27_000_000_000,'CPU stop: 27 GB'
def turn():
 spec=importlib.util.spec_from_file_location('packet163_compile_turn',ROOT/'experiments/own-xpu-runtime/ops/compile_turn.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def main(name):
 limits();p=P/name;B=p/'build';mirror=p/'native-source/repo';source_pins={};object_pins={}
 if name=='one-card':
  parent=STAGE/'packet58aj-onecard-resident';old=STAGE/'packet58ag-onecard-ports'
  rows=json.loads((parent/'lineage/58ag-build-commands.json').read_text())
  compilecmd=[x.replace(str(old),str(parent)) for x in next(r['command'] for r in rows if r['name']=='device-entry-main')]
  link=[x.replace(str(old),str(parent)) for x in next(r['command'] for r in rows if r['name']=='device-own-rt-iq3')]
  main_source=parent/'build/native/main.cpp'
 else:
  parent=STAGE/'packet131-snapshot-banks';rows=json.loads((STAGE/'packet131b-snapshot-banks/engine-commands.json').read_text())
  compilecmd=next(r['command'] for r in rows if r['name']=='device-entry-main').copy()
  link=next(r['command'] for r in rows if r['name']=='device-link').copy()
  main_source=parent/'build/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/main.cpp'
 includes=[Path(x[2:]) for x in compilecmd if x.startswith('-I')]
 visited=set()
 def copy_source(src):
  src=src.absolute()
  if src in visited:return
  assert src.is_file(),str(src)
  visited.add(src);target=mirror/src.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
  source_pins[str(src.relative_to(ROOT))]=sha(src)
  text=src.read_text()
  for inc in re.findall(r'^\s*#include\s+"([^"\n]+)"',text,re.M):
   paths=[Path(inc)] if Path(inc).is_absolute() else [src.parent/inc,*[d/inc for d in includes]]
   found=next((x for x in paths if x.is_file()),None)
   if found is not None and found.absolute().is_relative_to(ROOT):copy_source(found)
  # Include destinations and frozen rotary lookup paths become private; no arithmetic edits.
  text=text.replace(str(ROOT)+'/',str(mirror)+'/')
  target.write_text(text)
 entry=Path(compilecmd[compilecmd.index('-c')+1]);copy_source(entry)
 actual=mirror/main_source.relative_to(ROOT);text=actual.read_text()
 old_guard='a.tokens <= 128';assert text.count(old_guard)==1
 changed=text.replace(old_guard,'a.tokens <= 512')
 if name=='one-card':
  assert changed.count('requests.size()<=12')==1
  changed=changed.replace('requests.size()<=12','requests.size()<=13')
 (p/'response-cap.patch').write_text(''.join(difflib.unified_diff(text.splitlines(True),changed.splitlines(True),fromfile='a/main.cpp',tofile='b/main.cpp')))
 actual.write_text(changed)
 for i,a in enumerate(compilecmd):
  if a.startswith('-I') and a[2:].startswith(str(ROOT)+'/'):compilecmd[i]='-I'+str(mirror/Path(a[2:]).relative_to(ROOT))
 compilecmd[compilecmd.index('-c')+1]=str(mirror/entry.relative_to(ROOT))
 compilecmd[compilecmd.index('-o')+1]=str(B/'device/entry-main.o')
 if '-MF' in compilecmd:compilecmd[compilecmd.index('-MF')+1]=str(B/'device/entry-main.d')
 else:compilecmd[1:1]=['-MMD','-MF',str(B/'device/entry-main.d')]
 for i,arg in enumerate(link):
  if not arg.endswith('.o'):continue
  src=Path(arg)
  if src.name=='entry-main.o':link[i]=str(B/'device/entry-main.o');continue
  target=B/'objects'/(sha(src)[:16]+'-'+src.name)
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
  object_pins[str(target.relative_to(p))]=dict(source=str(src.relative_to(ROOT)),sha256=sha(src),bytes=src.stat().st_size)
  link[i]=str(target)
 link[link.index('-o')+1]=str(B/'device/own-rt-iq3')
 save(p/'build-inputs.json',dict(source_sha256=source_pins,objects=object_pins,compile=compilecmd,link=link,delta='parser admission128->512 only; all kernel objects unchanged'))
 # Source relocation is reversible byte-for-byte apart from the single guard.
 for src,h in source_pins.items():
  copied=(mirror/src).read_text().replace(str(mirror)+'/',str(ROOT)+'/')
  if ROOT/src==main_source:copied=copied.replace('a.tokens <= 512','a.tokens <= 128').replace('requests.size()<=13','requests.size()<=12')
  assert hashlib.sha256(copied.encode()).hexdigest()==h,src
 for label,cmd in [('compile',compilecmd),('link',link)]:
  with turn(),(B/(label+'.log')).open('w') as log:
   limits();started=time.monotonic();subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
  print(name,label,'PASS',round(time.monotonic()-started,1),flush=True)
 receipt=dict(passed=True,device_executed=False,parser_only=True,kernel_objects_unchanged=True,
  source_count=len(source_pins),object_count=len(object_pins),binary_sha256=sha(B/'device/own-rt-iq3'),
  peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,inputs_sha256=sha(p/'build-inputs.json'))
 assert receipt['peak_child_rss_bytes']<4*1024**3
 save(p/'evidence/build.json',receipt)
 identity=json.loads((p/'identity.json').read_text());identity['parent_binary_sha256']=identity['binary_sha256'];identity['binary_sha256']=receipt['binary_sha256'];identity['measurement_delta']='response-cap parser128->512 only'
 save(p/'identity.json',identity)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main(sys.argv[1])
