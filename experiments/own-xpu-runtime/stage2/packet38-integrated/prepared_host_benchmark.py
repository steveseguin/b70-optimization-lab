"""Compile/run CPU-only real submission front ends against an allocation-counted mock.

Requires current build/host objects. This does not load or run a device binary.
The mock records operation types and pointer order but never reads model data.
"""
import hashlib,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(argv):return ['nice','-n','19','ionice','-c','3','env','OMP_NUM_THREADS=2',*map(str,argv)]
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 scratch=P/'build/host-issue';scratch.mkdir(parents=True,exist_ok=True)
 os.environ['TMPDIR']=str(scratch)
 source=scratch/'benchmark.cpp';source.write_bytes((P/'prepared_issue_benchmark.cpp').read_bytes())
 checked=P/'build/checked'/P.relative_to(ROOT)
 flags=['-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fopenmp','-DOWN_RT_HOST_ONLY','-I'+str(checked)]
 obj=scratch/'benchmark.o';binary=scratch/'host-issue-benchmark'
 subprocess.run(command(['g++',*flags,'-c',source,'-o',obj]),check=True)
 objects=sorted((P/'build/gnu-host/CMakeFiles/programs.dir').rglob('*.o'))
 assert len(objects)>=18,'host programs not yet built'
 subprocess.run(command(['g++',*flags,obj,*objects,'-lcrypto','-Wl,--wrap=malloc','-Wl,--wrap=calloc','-Wl,--wrap=realloc','-o',binary]),check=True)
 affinity=sorted(os.sched_getaffinity(0));load=os.getloadavg()[0];start=time.monotonic()
 result=subprocess.run(command([binary]),text=True,capture_output=True)
 if result.returncode:raise RuntimeError(result.stderr+'\n'+result.stdout)
 receipt=json.loads(result.stdout)
 receipt.update(binary_sha256=sha(binary),source_sha256=sha(P/'prepared_issue_benchmark.cpp'),linked_objects={str(x.relative_to(P)):sha(x) for x in objects},compile_flags=flags,link_flags=['-fno-fast-math','-ffp-contract=off','-Wl,--wrap=malloc','-Wl,--wrap=calloc','-Wl,--wrap=realloc'],affinity=affinity,load1=load,wall_seconds=time.monotonic()-start,maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,limitation='Actual CPU front ends and common Device capture/issue owner path with a mock backend. Excludes SYCL runtime, driver submission, device arithmetic, Engine string/map dispatch, and native-only kernel splits. No device performance claim. Operation type plus pointers/order compared; not a complete serialized functor-argument proof.',allocation_hook='Global scalar/array/aligned new plus link --wrap malloc/calloc/realloc. Hooks count linked application calls; dynamically linked library internals are outside the mock issue path and not interposed.')
 (P/'prepared-host-benchmark.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps({k:receipt[k] for k in ('passed','device_executed','families','prepared_allocation_calls','binary_sha256','maxrss_kib')}))
 # Source/object are scratch; binary is retained for its receipt and reproducibility.
 source.unlink();obj.unlink()
if __name__=='__main__':main()
