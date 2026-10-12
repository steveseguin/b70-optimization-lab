"""Verify all four CMake dependency graphs against current sources; execute no binary."""
import gzip,json,os,subprocess,time
from pathlib import Path
from seal40 import P,B,MODES,artifacts,sha,save,compile_identity
from math_gate import closure
from storage import admit
def source_identity():
 paths=set(closure())|{P/'CMakeLists.txt',B/'fusion-rope.hpp'}
 paths.update(path for path in P.rglob('*') if path.is_file() and 'build' not in path.relative_to(P).parts and path.suffix in ('.cpp','.hpp'))
 paths.update(P/name for name in ('build_identity40.py','seal40.py','math_gate.py','storage.py'))
 return {os.path.relpath(path,P):sha(path) for path in sorted(paths)}
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and 1<=int(os.environ.get('OMP_NUM_THREADS','0'))<=4
 before_sources=source_identity();before_binaries=artifacts();rows=[];problems=[]
 for mode in MODES:
  admit(350_000_000);log=P/'evidence'/f'build-identity40-{mode}-{time.time_ns()}.log.gz';log.parent.mkdir(exist_ok=True)
  command=['nice','-n','19','ionice','-c','3','cmake','--build',str(B/mode),'-j1']
  with gzip.open(log,'wb') as output:
   child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
   while True:
    block=child.stdout.read(65536)
    if not block:break
    output.write(block)
   code=child.wait()
  rows.append(dict(mode=mode,command=command,returncode=code,log=str(log.relative_to(P)),log_sha256=sha(log)))
  if code:problems.append('build failed '+mode);break
 after_sources=source_identity();after_binaries=artifacts()
 if before_sources!=after_sources:problems.append('compile source closure changed during build verification')
 identity_errors,precision,links=compile_identity(P,after_binaries);problems.extend(identity_errors)
 changed={name:dict(before=before_binaries.get(name),after=digest) for name,digest in after_binaries.items() if before_binaries.get(name)!=digest}
 row=dict(schema='packet40.current-build-identity.v1',passed=not problems,device_executed=False,source_sha256=after_sources,sources_unchanged_during_build=before_sources==after_sources,binary_sha256=after_binaries,before_binary_sha256=before_binaries,changed_binaries=changed,dependency_graph_noop=not changed,rows=rows,precision=precision,link_commands=links,compile_jobs=1,problems=problems,scope='Current CMake dependency graph verification for GNU host, Intel host, ASAN host and device compilation, with before/after source and artifact identities. No runtime or device binary is executed. Rebuilt artifacts invalidate prior gates by binary identity.')
 save(P/'build-identity40.json',row)
 print(json.dumps(dict(passed=row['passed'],dependency_graph_noop=row['dependency_graph_noop'],changed_binaries=list(changed),problems=problems)),flush=True)
 if problems:raise RuntimeError('build identity verification failed')
if __name__=='__main__':main()
