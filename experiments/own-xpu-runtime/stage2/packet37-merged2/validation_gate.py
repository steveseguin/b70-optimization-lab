"""CPU twins traverse actual K1/K2 argument builders; no device discovery."""
import hashlib,json,os,resource,subprocess,time
from pathlib import Path
from cpu_gates import host
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 root=B/('validation-'+str(time.time_ns()));root.mkdir();results=[]
 for compiler in ('gnu-host','icpx-host'):
  for entry in ('nongemv-fixtures','k2-fixtures'):
   binary=B/compiler/entry;host(binary)
   for poison in (False,True):
    out=root/(compiler+'-'+entry+('-poison' if poison else ''));cmd=[str(binary),'--validate-only','--output',str(out)]
    if poison:cmd+=['--poison-dense-status']
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    if poison:
     assert r.returncode==1 and any(msg in r.stderr for msg in ('expanded dense geometry','p28 dense/routed contract')),(cmd,r.stderr)
    else:
     assert r.returncode==0,(cmd,r.stderr)
     receipt=json.loads((out/'receipt.json').read_text());assert receipt['validation_only'] and not receipt['device_executed'] and not receipt['reference_exact']
     rows=[json.loads(s) for s in (out/'validation-entries.jsonl').read_text().splitlines()]
     small_rows=[r for r in rows if r['class'].startswith('fusion:')]
     small_workloads={r['workload'] for r in small_rows};expected_small={'small.hc','small.gdn.ab','small.ffn.q6','small.ffn.q8'}
     if entry=='nongemv-fixtures':expected_small|={'small.mini.hc','small.mini.gdn.ab','small.mini.ffn'}
     assert small_workloads==expected_small
     for workload in small_workloads:
      arms=[r for r in small_rows if r['workload']==workload]
      assert {r['candidate'] for r in arms}=={'r5.sum.members',workload}
      assert {r['mode'] for r in arms}==({0} if entry=='k2-fixtures' else {0,1,2,3})
     rows=[r for r in rows if not r['class'].startswith('fusion:')]
     workloads={r['workload'] for r in rows};assert len(workloads)==34
     kernels=json.loads((P/'kernel-registry.json').read_text())['gemv']
     for workload in workloads:
      arm=[r for r in rows if r['workload']==workload];expert=arm[0]['count']>1
      expected=set(kernels[arm[0]['class']])
      assert {r['candidate'] for r in arm}==expected,(workload,arm)
      assert {r['mode'] for r in arm}==({0} if entry=='k2-fixtures' else {0,1,2,3,4,5})
      assert all(r['rows']==(2560 if workload=='expsdown' else 9 if r['mode']==4 else 8) for r in arm) if entry=='nongemv-fixtures' else all(r['rows']>=1 for r in arm)
     if entry=='k2-fixtures':
      events=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
      registry=json.loads((P/'k2-class-registry.json').read_text())['classes']
      assert {r['class'] for r in events}==set(registry)
      assert all({r['variant'] for r in events if r['class']==k}=={'packet18','specialised'} for k in registry)
     else:assert receipt['source_fixtures']==93 and receipt['fixtures']>93
    results.append(dict(compiler=compiler,entry=entry,poison=poison,returncode=r.returncode,binary_sha256=sha(binary),evidence=str(out.relative_to(B)),**({} if poison else dict(gemv_entry_calls=len(rows),small_entry_calls=len(small_rows),small_workloads=sorted(small_workloads),workloads=sorted(workloads),candidate_coverage={w:sorted({r['candidate'] for r in rows if r['workload']==w}) for w in sorted(workloads)},entry_trace_sha256=sha(out/'validation-entries.jsonl'),receipt_sha256=sha(out/'receipt.json')))))
  out=root/(compiler+'-continue');r=subprocess.run([str(B/compiler/'k2-fixtures'),'--validate-only','--inject-candidate-failures','--output',str(out)],capture_output=True,text=True,timeout=120)
  assert r.returncode==0,r.stderr
  failures=[json.loads(s) for s in (out/'candidate-failures.jsonl').read_text().splitlines()]
  assert {r['class'] for r in failures}=={'norm','streams','gemv:gdn.qkv'}
  events=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
  assert any(r['class']=='gemv:logits' and r['variant']=='specialised' for r in events)
  results.append(dict(compiler=compiler,continued_after_failures=sorted({r['class'] for r in failures})))
 report=dict(passed=True,device_executed=False,scope='K1 and K2 argument validation, every registered class and linked candidate; exact production K2 extents; no arithmetic in validate-only mode',checks=results,maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 (P/'validation-gates.json').write_text(json.dumps(report,indent=2)+'\n');print('all fixture entry validations and poison/continuation controls PASS')
if __name__=='__main__':main()
