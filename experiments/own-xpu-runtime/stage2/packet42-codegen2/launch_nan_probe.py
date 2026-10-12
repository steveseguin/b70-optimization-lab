"""CPU-only diagnostic of baseline NaN payload selection; not a passing gate."""
import hashlib,json,os,resource,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build/tiny'
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
if shutil.disk_usage('/').free<8*1024**3:raise SystemExit('STOP filesystem below8GiB')
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));os.environ['TMPDIR']=str(B)
receipt=json.loads((P/'tiny-build-receipt.json').read_text());cmd=next(c['argv'] for c in receipt['commands'] if 'tiny-cpu-icpx' in c['argv'][-1]);cmd=[a for a in cmd if a!='-fp-model=strict'];cmd[-1]=str(B/'nan-default')
r=subprocess.run(cmd,text=True,capture_output=True);assert r.returncode==0,r.stderr
rows=[]
for label,binary in [('default',B/'nan-default'),('strict',B/'tiny-cpu-icpx')]:
 r=subprocess.run([str(binary),'--nan-probe'],text=True,capture_output=True);rows.append(dict(label=label,argv=[str(binary),'--nan-probe'],returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()))
f=P/'tiny-diagnostics.json';d=json.loads(f.read_text());d['records'][0].update(exact_compile_argv=cmd,raw_cpu_results=rows);f.write_text(json.dumps(d,indent=2)+'\n');(B/'nan-default').unlink();print(json.dumps(rows,indent=2))
