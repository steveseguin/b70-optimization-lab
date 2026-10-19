"""GNU/Intel synthetic byte gate plus inheritance of packet175's (packet166's) real-weight oracle.

No GGUF read. The host arms A (bundle-8 dense lane) and B (D1 scale-word multicast,
emulated subgroup) must be byte-identical, GNU and Intel traces must agree, both
compilers must pass the D1 self-test (coverage proof plus random-bit lane-sum equality
against p68c::dense_lane for Q6_K and Q8_0), and the arm-A reference must equal
packet175's own GNU/Intel synthetic trace at position 31 for every buffer. That proves
the host path is packet175's (hence packet166's) arithmetic, so the agreed real-weight
oracle that packet175 inherited from packet166 is the device anchor for this micro.
"""
import json,resource,subprocess,time
from pathlib import Path
from build_engine import limits,P,ROOT,sha
import launch_env

PARENT=P.parent/'packet175-twocard-d2-micro'
GRANDPARENT=P.parent/'packet166-m2-layer-micro'


def native_rows(path,position=31):
 rows=[json.loads(s) for s in Path(path).read_text().splitlines()]
 assert rows[-1]['passed'] and rows[-1]['zero_errors'] and rows[-1]['finite_outputs'] and rows[-1]['backend']=='cpu'
 data={(r['layer'],r['position'],r['buffer']):(r['compared_bytes'],r['sha256']) for r in rows if r['kind']=='bytes' and r['position']==position}
 assert all(r['different_bytes']==0 for r in rows if r['kind']=='bytes')
 return data


def selftest(path):
 rows=[json.loads(s) for s in Path(path).read_text().splitlines()]
 tests=[r for r in rows if r.get('kind')=='d1_selftest']
 assert len(tests)==1 and tests[0]['passed'] is True and tests[0]['coverage_tiles']>0 and tests[0]['lane_sums_compared']>0,'D1 self-test missing'
 assert rows[-1].get('variant')=='d1-scale-multicast','D1 variant summary missing'
 return dict(coverage_tiles=tests[0]['coverage_tiles'],lane_sums_compared=tests[0]['lane_sums_compared'])


def ref(name,path):
 return dict(name=name,parent_relpath=str(path.relative_to(ROOT)),parent_digest=sha(path))


def main():
 limits()
 build=json.loads((P/'evidence/build.json').read_text());assert all(sha(ROOT/f)==h for r in build['records'] for f,h in r['sources'].items()),'native source pins stale: rebuild before CPU qualification'
 out=P/'evidence'/('cpu-synthetic-'+str(time.time_ns()));out.mkdir()
 records=[];traces=[];tests=[]
 for compiler in ('gnu-host','intel-host'):
  binary=P/'build'/('d1-micro-'+compiler);help_=subprocess.run([str(binary),'--help'],env=launch_env.environment(),stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
  argv=['/usr/bin/ionice','-c3',str(binary),'--rank','0','--mode','cpu','--weights','synthetic','--repeats','240']
  assert all(v in help_.stdout for v in argv[3:] if v.startswith('--'))
  stdout=out/(compiler+'.jsonl');stderr=out/(compiler+'.stderr')
  with stdout.open('x') as so,stderr.open('x') as se:
   result=subprocess.run(argv,env=launch_env.environment(),stdin=subprocess.DEVNULL,stdout=so,stderr=se)
  records.append(dict(compiler=compiler,argv=argv,returncode=result.returncode,binary_sha256=sha(binary),stdout=str(stdout.relative_to(ROOT)),stdout_sha256=sha(stdout)))
  if result.returncode:
   (out/'failure.json').write_text(json.dumps(dict(passed=False,records=records),indent=2)+'\n');raise RuntimeError('native CPU gate failed; see '+str(stderr))
  traces.append(native_rows(stdout));tests.append(selftest(stdout))
 assert traces[0]==traces[1],'GNU/Intel bytes differ'
 assert tests[0]==tests[1],'GNU/Intel D1 self-test coverage differs'
 # Parent equality at position 31 (packet175 synthetic GNU and Intel traces, every buffer).
 parent_gate=json.loads((PARENT/'evidence/cpu-synthetic-parity.json').read_text());assert parent_gate['passed'] and parent_gate['host_ab_byte_identical']
 parent_traces=[native_rows(ROOT/r['stdout']) for r in parent_gate['records']]
 assert parent_traces[0]==parent_traces[1]
 mine=traces[0];parent=parent_traces[0]
 assert set(mine)==set(parent),'buffer set differs from packet175'
 matched=0
 for key,value in parent.items():
  assert mine[key]==value,'host arithmetic differs from packet175: '+str(key);matched+=1
 # Inherit packet175's real-weight oracle (packet166's position-31 rows) unchanged.
 parent_oracle=PARENT/'evidence/real-oracle.tsv';parent_inherit=json.loads((PARENT/'evidence/oracle-inheritance.json').read_text())
 assert parent_inherit['passed'] and parent_inherit['oracle_sha256']==sha(parent_oracle)
 for row in parent_inherit['parents']:
  assert sha(ROOT/row['parent_relpath'])==row['parent_digest'],'packet175 oracle parent changed: '+row['name']
 lines=parent_oracle.read_text().splitlines()
 keys=[(int(x.split()[0]),int(x.split()[1]),x.split()[2]) for x in lines]
 assert len(lines)==parent_inherit['oracle_rows']==len(set(keys)) and all(k in parent and k[1]==31 for k in keys),'oracle rows must name traced position-31 buffers'
 oracle=P/'evidence/real-oracle.tsv';oracle.write_text('\n'.join(lines)+'\n');assert sha(oracle)==sha(parent_oracle)
 parent_device=GRANDPARENT/'evidence/layer-micro-B1/samples.jsonl'
 summary=json.loads(parent_device.read_text().splitlines()[-1]);assert summary['cpu_oracle_match'] and summary['backend']=='device' and summary['passed']
 row=dict(passed=True,real_weights=False,synthetic_weights=True,device_executed=False,compiler_exactness=True,host_ab_byte_identical=True,
          d1_selftest=tests[0],compared_buffers=len(mine),parent_matched_buffers=matched,records=records,
          peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024)
 assert row['peak_rss_bytes']<=4*1024**3
 (out/'result.json').write_text(json.dumps(row,indent=2)+'\n')
 (P/'evidence/cpu-synthetic-parity.json').write_text(json.dumps(row,indent=2)+'\n')
 inheritance=dict(schema='own-runtime.packet175b.oracle-inheritance.v1',passed=True,model_reads=False,position=31,
   oracle_rows=len(lines),oracle_sha256=sha(oracle),
   parents=[ref('packet175 inherited real-weight oracle',parent_oracle),ref('packet175 oracle inheritance receipt',PARENT/'evidence/oracle-inheritance.json'),
            ref('packet175 synthetic CPU parity receipt',PARENT/'evidence/cpu-synthetic-parity.json'),
            ref('packet166 lane-B device stream (cpu_oracle_match true)',parent_device)],
   reason='packet175b host reference equals packet175 synthetic trace for every buffer at position 31 (GNU and Intel); '
          'arm B (D1) is byte-identical to arm A on both compilers; the packet166 real oracle carried by packet175 carries over.')
 (P/'evidence/oracle-inheritance.json').write_text(json.dumps(inheritance,indent=2)+'\n')
 print(json.dumps(dict(passed=True,compared_buffers=len(mine),parent_matched=matched,oracle_rows=len(lines),d1_selftest=tests[0])));return 0
if __name__=='__main__':raise SystemExit(main())
