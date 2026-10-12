"""Verify all four CMake dependency graphs against current sources; execute no binary."""
import gzip,json,os,re,subprocess,time
from pathlib import Path
from seal40 import P,B,MODES,artifacts,sha,save,compile_identity
from math_gate import closure
from storage import admit
def source_identity():
 paths=set(closure())|{P/'CMakeLists.txt',B/'fusion-rope.hpp'}
 paths.update(path for path in P.rglob('*') if path.is_file() and 'build' not in path.relative_to(P).parts and path.suffix in ('.cpp','.hpp'))
 paths.update(P/name for name in ('build_identity40.py','seal40.py','math_gate.py','storage.py','kernel_gate.py','kernel_overlay.py','submission_overlay.py','validation_mirror.py'))
 return {os.path.relpath(path,P):sha(path) for path in sorted(paths)}
GENERATORS=('kernel_gate.py','kernel_overlay.py','submission_overlay.py','validation_mirror.py','math_gate.py')
def mirror_files(build):
 paths=set((build/'checked').rglob('*'))|set(build.glob('jit-*.cpp'))
 for mode in MODES:
  if mode!='device':paths.update((build/mode/'validation').glob('*'))
 return sorted(path for path in paths if path.is_file())
def mirror_identity(build):return {str(path.relative_to(build)):sha(path) for path in mirror_files(build)}
def regenerate_mirrors(packet=P,build=B,*,kernel=None,validation=None,sources=None):
 """Refresh actual compiler inputs, preserving mtimes only for identical bytes."""
 if kernel is None:
  from kernel_gate import mirror
  kernel=mirror
 if validation is None:
  from validation_mirror import generate
  validation=generate
 sources=sources or source_identity
 before_sources=sources();before=mirror_identity(build)
 times={path:(path.stat().st_atime_ns,path.stat().st_mtime_ns) for path in mirror_files(build)}
 mapping=kernel()
 for target in mapping.values():
  target=Path(target).resolve()
  if build.resolve() not in target.parents or not target.is_file():raise ValueError('missing/outside generated kernel mirror')
 for mode in MODES:
  if mode!='device':validation(build/mode/'validation')
 after=mirror_identity(build)
 if not mapping or not after:raise ValueError('empty compiler mirror inventory')
 for path,timestamps in times.items():
  key=str(path.relative_to(build))
  if key in after and before[key]==after[key]:os.utime(path,ns=timestamps)
 if sources()!=before_sources:raise ValueError('source changed during mirror generation')
 return dict(regenerated=True,before_sha256=before,actual_sha256=after,
  changed=[name for name,digest in after.items() if before.get(name)!=digest],
  generator_sha256={name:sha(packet/name) for name in GENERATORS},source_sha256=before_sources)
def verify_mirror_receipt(row,packet=P,build=B):
 if row.get('mirror_second_refresh_unchanged') is not True or row.get('dependency_graph_noop') is not True:
  raise ValueError('mirror/dependency no-op proof missing')
 mirrors=row.get('mirror_sha256',{})
 if not mirrors or mirrors!=mirror_identity(build):raise ValueError('actual compiler mirrors differ from build proof')
 regenerated=row.get('mirror_regeneration',{})
 if regenerated.get('regenerated') is not True or regenerated.get('actual_sha256')!=mirrors:
  raise ValueError('fresh mirror generation proof missing')
 expected={name:sha(packet/name) for name in GENERATORS}
 if row.get('mirror_generator_sha256')!=expected or regenerated.get('generator_sha256')!=expected:
  raise ValueError('mirror generator/overlay identity changed')
 return True

def build_pass(label):
 rows=[];problems=[]
 for mode in MODES:
  admit(350_000_000);log=P/'evidence'/f'build-identity40-{label}-{mode}-{time.time_ns()}.log.gz';log.parent.mkdir(exist_ok=True)
  command=['nice','-n','19','ionice','-c','3','cmake','--build',str(B/mode),'-j1'];actions=[]
  with gzip.open(log,'wb') as output:
   child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
   for block in iter(child.stdout.readline,b''):
    output.write(block)
    if re.search(rb'Building (?:CXX|C) object|Linking (?:CXX|C)|Generating ',block):actions.append(block.decode(errors='replace').strip())
   code=child.wait()
  rows.append(dict(pass_name=label,mode=mode,command=command,returncode=code,build_actions=actions,log=str(log.relative_to(P)),log_sha256=sha(log)))
  if code:problems.append('build failed '+label+'/'+mode);break
 return rows,problems
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and 1<=int(os.environ.get('OMP_NUM_THREADS','0'))<=4
 admit(32_000_000)
 before_sources=source_identity();before_binaries=artifacts()
 mirrors=regenerate_mirrors();rows,problems=build_pass('refresh')
 refreshed_binaries=artifacts();refreshed_mirrors=mirror_identity(B)
 if mirrors['actual_sha256']!=refreshed_mirrors:problems.append('compiler mirror bytes changed during dependency build')
 # A second refresh must reproduce the same bytes; identical validation outputs
 # keep their timestamps so the following graph walk is a genuine no-op check.
 check=regenerate_mirrors()
 if check['actual_sha256']!=refreshed_mirrors or check['changed']:problems.append('mirror regeneration is not idempotent')
 noop_rows,noop_problems=build_pass('noop');rows.extend(noop_rows);problems.extend(noop_problems)
 after_sources=source_identity();after_binaries=artifacts();after_mirrors=mirror_identity(B)
 if before_sources!=after_sources:problems.append('compile source closure changed during build verification')
 if after_mirrors!=refreshed_mirrors:problems.append('compiler mirror bytes changed during no-op verification')
 noop=refreshed_binaries==after_binaries and not any(r['build_actions'] for r in noop_rows)
 if not noop:problems.append('second dependency build was not a no-op')
 identity_errors,precision,links=compile_identity(P,after_binaries);problems.extend(identity_errors)
 changed={name:dict(before=before_binaries.get(name),after=digest) for name,digest in after_binaries.items() if before_binaries.get(name)!=digest}
 row=dict(schema='packet40.current-build-identity.v1',passed=not problems,device_executed=False,source_sha256=after_sources,
  sources_unchanged_during_build=before_sources==after_sources,binary_sha256=after_binaries,before_binary_sha256=before_binaries,
  changed_binaries=changed,dependency_graph_noop=noop,mirror_regeneration=mirrors,mirror_sha256=after_mirrors,
  mirror_generator_sha256=mirrors['generator_sha256'],mirror_second_refresh_unchanged=not check['changed'],
  rows=rows,precision=precision,link_commands=links,compile_jobs=1,problems=problems,
  scope='Regenerate checked/JIT and host validation compiler inputs from current sources, bind actual mirror bytes and generator/overlay identities, build all four modes then require a second dependency pass with no compile/link actions or artifact changes. No runtime or device binary executed; rebuilt artifact hashes invalidate old gates.')
 save(P/'build-identity40.json',row)
 print(json.dumps(dict(passed=row['passed'],dependency_graph_noop=noop,changed_binaries=list(changed),mirror_changes=len(mirrors['changed']),problems=problems)),flush=True)
 if problems:raise RuntimeError('build identity verification failed')
if __name__=='__main__':main()
