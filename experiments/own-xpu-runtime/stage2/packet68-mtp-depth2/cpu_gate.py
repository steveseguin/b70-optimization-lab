"""Six synthetic target-half rows and discarded state; no CPU model run."""
import hashlib,json,os,resource,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 assert not (P/'screen-seal.json').exists()
 commands=json.loads((P/'engine-commands.json').read_text())
 cc=next(x['command'] for x in commands if x['name']=='gnu-host-entry-main');cc=cc[:cc.index('-o')]
 link=next(x['command'] for x in commands if x['name']=='fixture-link')
 link=[str(B/'reference-fixture.o') if x==str(B/'probe_fixture.o') else x for x in link]
 link[link.index('-o')+1]=str(B/'reference-fixture')
 for cmd in ([*cc,'-o',str(B/'reference-fixture.o'),'-c',str(B/'reference-fixture.cpp')],link):
  r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True);assert r.returncode==0,r.stderr
 rows=[]
 for name,binary,mode in [('reference','reference-fixture','off'),('off','probe-fixture','off'),('on','probe-fixture','on'),('repeat','probe-fixture','on')]:
  dest=P/'fixture'/name
  cmd=[str(B/binary),str(dest),mode]
  r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90);assert r.returncode==0,r.stderr
  rows.append(dict(name=name,command=cmd,stdout=r.stdout,stderr=r.stderr,sha256=sha(dest/'state.bin')))
 assert len({r['sha256'] for r in rows})==1
 f=P/'fixture';(f/'expected.bin').write_bytes((f/'reference/state.bin').read_bytes());(f/'actual.bin').write_bytes((f/'on/state.bin').read_bytes())
 build=json.loads((P/'build-device-receipt.json').read_text());build['sources'][str((P/'cpu_gate.py').relative_to(ROOT))]=sha(P/'cpu_gate.py');save(P/'build-device-receipt.json',build)
 sources={str(path.relative_to(ROOT)):sha(path) for path in (P/'cpu_gate.py',P/'probe_fixture.cpp',B/'reference-fixture.cpp',B/'reference-fixture',P/'rank.hpp')}
 save(f/'receipt.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
  changed_class='M=1/2/3 sequential target-half fixture versus frozen packet64; full plan-buffer, spare-bank, history, extent and shared-slot identity after discarded rows',
  command=['python3','-B',str(P/'cpu_gate.py')],build_receipt_sha256=sha(P/'build-device-receipt.json'),sources=sources,
  expected=dict(path='fixture/expected.bin',sha256=sha(f/'expected.bin')),actual=dict(path='fixture/actual.bin',sha256=sha(f/'actual.bin')),runs=rows,
  full_cpu_model_runs=0,limitations='Synthetic two-layer half only; real model device exactness pending. M means sequential row count, not a batched kernel.'))
 print('PASS: packet64 target rows 1/2/3 and discarded-row state identity, two fresh repeats')
if __name__=='__main__':main()
