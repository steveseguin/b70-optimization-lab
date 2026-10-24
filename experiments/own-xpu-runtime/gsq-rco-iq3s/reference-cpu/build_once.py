"""Root-owned bounded CPU reference build; no model or reference executable run."""
from pathlib import Path
import hashlib,json,os,resource,signal,subprocess,time
P=Path(__file__).resolve().parent
def need(v,m):
 if not v:raise RuntimeError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def usage(root):
 total=0
 for p in root.rglob('*'):
  try:
   if p.is_file():total+=p.stat().st_size
  except FileNotFoundError:pass # Compiler temporary files may disappear.
 return total
def main():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement')
 recipe=json.loads((P/'build-recipe.json').read_text());review=json.loads((P/'evidence/independent-build-source-review.json').read_text());need(review['passed'],'independent build source review')
 for f,h in recipe['source_sha256'].items():need(sha(f)==h,'recipe source drift '+f)
 src=Path(recipe['source_root']);out=Path(recipe['output_root']);limits=recipe['build_limits']
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=src,text=True).strip();need(head==recipe['source_head'],'source HEAD')
 need(not subprocess.check_output(['git','status','--porcelain'],cwd=src),'clean reference source')
 need(not out.exists() and Path('/mnt/usb-models').stat().st_dev==2050,'fresh expected USB build root')
 need(os.statvfs('/').f_bavail*os.statvfs('/').f_frsize>=limits['root_free_floor_bytes'],'root reserve')
 need(os.statvfs('/mnt/usb-models').f_bavail*os.statvfs('/mnt/usb-models').f_frsize>=2*1024**3+limits['output_quota_bytes'],'USB build forecast and reserve')
 out.mkdir(parents=True,mode=0o700)
 for name in ('tmp','cwd','empty-backends'):out.joinpath(name).mkdir(mode=0o700)
 files=subprocess.check_output(['git','ls-files','-z'],cwd=src).decode().split('\0');inventory=[]
 for name in filter(None,files):
  f=src/name
  if f.is_file():inventory.append(dict(path=name,bytes=f.stat().st_size,sha256=sha(f),symlink=f.is_symlink()))
 save(out/'source-inventory.json',dict(head=head,clean=True,files=inventory))
 env={k:os.environ[k] for k in ('HOME','USER','LOGNAME','LANG') if k in os.environ}
 env.update(PATH='/usr/bin:/bin',LC_ALL='C',TMPDIR=str(out/'tmp'),CCACHE_DISABLE='1',CMAKE_BUILD_PARALLEL_LEVEL='2',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
 resource.setrlimit(resource.RLIMIT_AS,(limits['address_space_bytes'],limits['address_space_bytes']))
 start=time.monotonic();proc=None;receipt=dict(passed=False,source_head=head,recipe_sha256=sha(P/'build-recipe.json'),driver_sha256=sha(__file__),review_sha256=sha(P/'evidence/independent-build-source-review.json'),source_inventory_sha256=sha(out/'source-inventory.json'),model_loaded=False,reference_executable_invoked=False,phases=[])
 try:
  for phase,argv in [('configure',recipe['configure_argv']),('build',recipe['build_argv'])]:
   log=out/(phase+'.log');begin=time.monotonic()
   with log.open('xb') as f:
    proc=subprocess.Popen(argv,cwd=out/'cwd',env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    violation=None
    while proc.poll() is None:
     size=usage(out)
     rootfree=os.statvfs('/').f_bavail*os.statvfs('/').f_frsize;usbfree=os.statvfs('/mnt/usb-models').f_bavail*os.statvfs('/mnt/usb-models').f_frsize
     if size>limits['output_quota_bytes'] or rootfree<limits['root_free_floor_bytes'] or usbfree<2*1024**3 or time.monotonic()-start>limits['deadline_seconds']:
      violation=dict(output_bytes=size,root_free=rootfree,usb_free=usbfree,elapsed=time.monotonic()-start);os.killpg(proc.pid,signal.SIGTERM);proc.wait();break
     time.sleep(2)
    rc=proc.wait()
   row=dict(phase=phase,argv=argv,returncode=rc,elapsed_seconds=time.monotonic()-begin,log_sha256=sha(log),violation=violation);receipt['phases'].append(row);print(json.dumps(row),flush=True)
   need(rc==0 and violation is None,'bounded '+phase+' failed')
  binary=out/'build/bin/llama-server';need(binary.is_file(),'CPU server produced')
  need(not subprocess.check_output(['git','status','--porcelain'],cwd=src),'source remains clean')
  for row in inventory:need(sha(src/row['path'])==row['sha256'],'source changed while building')
  size=usage(out);need(size<=limits['output_quota_bytes'],'final output quota')
  receipt.update(passed=True,binary=str(binary),binary_sha256=sha(binary),output_bytes=size,elapsed_seconds=time.monotonic()-start,runtime_admitted=False)
 except BaseException as e:
  receipt['error']=repr(e)
  if proc is not None and proc.poll() is None:os.killpg(proc.pid,signal.SIGTERM);receipt['compiler_cooperative_exit']=proc.wait()
  raise
 finally:save(P/'evidence/build-result.json',receipt)
 print(json.dumps({k:receipt[k] for k in ('passed','binary_sha256','output_bytes','elapsed_seconds','runtime_admitted')}),flush=True)
if __name__=='__main__':main()
