"""GNU/Intel synthetic byte gate plus inheritance of packet166's real-weight oracle.

No GGUF read. The host arms A (baseline) and B (warm-ahead) must be byte-identical,
GNU and Intel traces must agree, and the arm-A reference must equal packet166's own
GNU/Intel synthetic trace at position 31 buffer by buffer. That proves the host path
is packet166's arithmetic, so packet166's agreed real-weight oracle (which its lane-B
device run of 2026-10-19 matched) is the device anchor for this micro.
"""
import json,resource,subprocess,time
from pathlib import Path
from build_engine import limits,P,ROOT,sha
import launch_env

PARENT=P.parent/'packet166-m2-layer-micro'
EXTRA={'warm.scratch','warm.never.scratch'}


def native_rows(path,position=31):
 rows=[json.loads(s) for s in Path(path).read_text().splitlines()]
 assert rows[-1]['passed'] and rows[-1]['zero_errors'] and rows[-1]['finite_outputs'] and rows[-1]['backend']=='cpu'
 data={(r['layer'],r['position'],r['buffer']):(r['compared_bytes'],r['sha256']) for r in rows if r['kind']=='bytes' and r['position']==position}
 assert all(r['different_bytes']==0 for r in rows if r['kind']=='bytes')
 return data


def ref(name,path):
 return dict(name=name,parent_relpath=str(path.relative_to(ROOT)),parent_digest=sha(path))


def main():
 limits()
 build=json.loads((P/'evidence/build.json').read_text());assert all(sha(ROOT/f)==h for r in build['records'] for f,h in r['sources'].items()),'native source pins stale: rebuild before CPU qualification'
 out=P/'evidence'/('cpu-synthetic-'+str(time.time_ns()));out.mkdir()
 records=[];traces=[]
 for compiler in ('gnu-host','intel-host'):
  binary=P/'build'/('d2-micro-'+compiler);help_=subprocess.run([str(binary),'--help'],env=launch_env.environment(),stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
  argv=['/usr/bin/ionice','-c3',str(binary),'--rank','0','--mode','cpu','--weights','synthetic','--repeats','240']
  assert all(v in help_.stdout for v in argv[3:] if v.startswith('--'))
  stdout=out/(compiler+'.jsonl');stderr=out/(compiler+'.stderr')
  with stdout.open('x') as so,stderr.open('x') as se:
   result=subprocess.run(argv,env=launch_env.environment(),stdin=subprocess.DEVNULL,stdout=so,stderr=se)
  records.append(dict(compiler=compiler,argv=argv,returncode=result.returncode,binary_sha256=sha(binary),stdout=str(stdout.relative_to(ROOT)),stdout_sha256=sha(stdout)))
  if result.returncode:
   (out/'failure.json').write_text(json.dumps(dict(passed=False,records=records),indent=2)+'\n');raise RuntimeError('native CPU gate failed; see '+str(stderr))
  traces.append(native_rows(stdout))
 assert traces[0]==traces[1],'GNU/Intel bytes differ'
 # Parent equality at position 31 (packet166 synthetic GNU and Intel traces).
 parent_gate=json.loads((PARENT/'evidence/cpu-synthetic-parity.json').read_text());assert parent_gate['passed']
 parent_traces=[native_rows(ROOT/r['stdout']) for r in parent_gate['records']]
 assert parent_traces[0]==parent_traces[1]
 mine=traces[0];parent=parent_traces[0]
 assert {k[2] for k in mine}=={k[2] for k in parent}|EXTRA,'buffer set differs from packet166 beyond the warm sink'
 matched=0
 for key,value in parent.items():
  assert mine[key]==value,'host arithmetic differs from packet166: '+str(key);matched+=1
 # Inherit packet166's agreed real-weight oracle rows for position 31 only.
 parent_oracle=PARENT/'evidence/real-oracle.tsv';parent_real=json.loads((PARENT/'evidence/cpu-real-parity.json').read_text())
 assert parent_real['passed'] and parent_real['real_weights'] and parent_real['oracle_sha256']==sha(parent_oracle)
 lines=[l for l in parent_oracle.read_text().splitlines() if l.split()[1]=='31']
 assert sorted(tuple(l.split()[:3]) for l in lines)==sorted((str(l),str(p),n) for (l,p,n) in parent),'parent oracle rows differ from parent position-31 buffers'
 oracle=P/'evidence/real-oracle.tsv';oracle.write_text('\n'.join(lines)+'\n')
 parent_device=PARENT/'evidence/layer-micro-B1/samples.jsonl'
 summary=json.loads(parent_device.read_text().splitlines()[-1]);assert summary['cpu_oracle_match'] and summary['backend']=='device' and summary['passed']
 row=dict(passed=True,real_weights=False,synthetic_weights=True,device_executed=False,compiler_exactness=True,host_ab_byte_identical=True,
          compared_buffers=len(mine),parent_matched_buffers=matched,records=records,
          peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024)
 assert row['peak_rss_bytes']<=4*1024**3
 (out/'result.json').write_text(json.dumps(row,indent=2)+'\n')
 (P/'evidence/cpu-synthetic-parity.json').write_text(json.dumps(row,indent=2)+'\n')
 inheritance=dict(schema='own-runtime.packet175.oracle-inheritance.v1',passed=True,model_reads=False,position=31,
   oracle_rows=len(lines),oracle_sha256=sha(oracle),
   parents=[ref('packet166 real-weight oracle',parent_oracle),ref('packet166 real CPU parity receipt',PARENT/'evidence/cpu-real-parity.json'),
            ref('packet166 synthetic CPU parity receipt',PARENT/'evidence/cpu-synthetic-parity.json'),
            ref('packet166 lane-B device stream (cpu_oracle_match true)',parent_device)],
   reason='packet175 host reference equals packet166 synthetic trace for all parent buffers at position 31 (GNU and Intel); '
          'arm B is byte-identical to arm A on both compilers; packet166 real oracle and device match carry over.')
 (P/'evidence/oracle-inheritance.json').write_text(json.dumps(inheritance,indent=2)+'\n')
 print(json.dumps(dict(passed=True,compared_buffers=len(mine),parent_matched=matched,oracle_rows=len(lines))));return 0
if __name__=='__main__':raise SystemExit(main())
