"""CPU-only private entry build, serialized through the frozen compiler turn."""
import hashlib, importlib.util, json, os, resource, shutil, subprocess, time
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
STAGE=P.parent
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,r):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
def limits():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage(P).free>=27_000_000_000,'CPU stop:27GB'
def turn():
    spec=importlib.util.spec_from_file_location('p168_compile_turn',P.parents[1]/'ops/compile_turn.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod.turn()
def main():
    limits();commands=json.loads((P/'lineage/build-inputs.json').read_text());rows=[]
    inputs={str(f.relative_to(P)):sha(f) for f in [P/'native_probe.hpp',P/'lineage/build-inputs.json',*sorted((P/'native-source').rglob('*.hpp')),*sorted((P/'native-source').rglob('*.cpp'))]}
    for label in ('compile','link'):
        with turn(),(P/'build'/f'{label}.log').open('w') as log:
            start=time.monotonic()
            subprocess.run(commands[label],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
        rows.append(dict(stage=label,seconds=time.monotonic()-start))
        print(label,'PASS',flush=True)
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024
    assert rss<=4*1024**3
    assert all(sha(P/n)==h for n,h in inputs.items()),'native source changed during build'
    save(P/'evidence/build.json',dict(passed=True,device_executed=False,commands=rows,inputs_sha256=inputs,peak_child_rss_bytes=rss,binary_sha256=sha(P/'build/device/own-rt-iq3')))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
