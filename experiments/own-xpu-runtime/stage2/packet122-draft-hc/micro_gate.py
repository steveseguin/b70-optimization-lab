"""Fresh-process exactness and per-class 20% kill gate; never launches devices."""
import argparse,json,statistics,hashlib,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
CLASSES=('draft.blk.0.hc.a.gate','draft.blk.0.hc.f.gate','draft.final.gate')
def require(v,m):
 if not v:raise ValueError(m)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify(root,rows):
 for n,h in rows.items():require(sha(root/n)==h,'changed input '+n)
def prerequisites(packet=P):
 b=read(packet/'evidence/microbench-build.json');require(b['passed'] is True and b['device_executed'] is False,'CPU micro build');verify(ROOT,b['sources']);verify(packet,b['artifacts'])
 c=read(packet/'evidence/cpu-byte-identity.json');require(c['passed'] is True and c['device_executed'] is False,'CPU bytes');verify(ROOT,c['sources'])
 for n,r in c['generated_sources'].items():require(sha(ROOT/n)==r['sha256'] and sha(ROOT/r['source'])==r['source_sha256'],'CPU generated source changed')
 runs=c['views']['p122']['runs'];require(len(runs)==4 and {(r['compiler'],r['repeat']) for r in runs}=={(c,n) for c in ('GNU','Intel') for n in (1,2)},'four fresh CPU byte runs')
 for r in runs:
  require(r['passed'] is True and r['expected_sha256']==r['candidate_sha256'] and r['cases']==16,'CPU mismatch or incomplete cases')
  require(hashlib.sha256(gzip.decompress((ROOT/r['raw_evidence']).read_bytes())).hexdigest()==r['expected_sha256'],'retained bytes changed')
 for r in c['compilers']:require(sha(ROOT/r['binary'])==r['binary_sha256'],'CPU binary changed')
 return dict(build_sha256=sha(packet/'evidence/microbench-build.json'),cpu_sha256=sha(packet/'evidence/cpu-byte-identity.json'),binary_sha256=sha(packet/'build/microbench'))
def analyze(rows):
 samples={}
 for r in rows:
  context,iteration,view=r['context'],r['iteration'],r['view'];key=(context,iteration,view)
  require(context in (128,4096) and type(iteration) is int and 0<=iteration<50 and view in ('production','p122') and key not in samples,'unexpected/duplicate sample')
  require(r['warmup'] is (iteration<10),'warmup label')
  require(r['order']==((view=='p122')^(iteration&1)),'interleaved paired order')
  require(all(type(v) is int and v>0 for v in r['classes_ns'].values()),'invalid class duration')
  require(sum(r['classes_ns'].values())==r['gpu_ns'] and len(r['events'])==r['submissions']>0,'incomplete event accounting')
  totals={}
  for event in r['events']:
   delta=event['end_ns']-event['start_ns'];require(event['start_ns']>0 and 0<delta<=4_000_000_000,'invalid event interval');totals[event['class']]=totals.get(event['class'],0)+delta
  require(totals==r['classes_ns'],'event/class disagreement')
  require(set(CLASSES)<=set(totals),'missing changed HC class')
  samples[key]=r
 require(len(samples)==200,'complete 2 contexts x50 pairs required')
 ratios={};qualified=True
 for context in (128,4096):
  for cls in (*CLASSES,'sum_changed_classes'):
   groups=[[],[]]
   for iteration in range(10,50):
    a,b=[samples[context,iteration,v]['classes_ns'] for v in ('production','p122')]
    ratio=(sum(b[k] for k in CLASSES)/sum(a[k] for k in CLASSES)) if cls=='sum_changed_classes' else b[cls]/a[cls]
    groups[iteration&1].append(ratio)
   orders=[statistics.median(v) for v in groups];overall=statistics.median(groups[0]+groups[1]);passed=overall<=.8 and max(orders)<=.8;qualified &= passed
   ratios[f'{context}:{cls}']=dict(ratio=overall,order_ratios=orders,qualified=passed)
 return dict(passed=True,qualified=['p122'] if qualified else [],ratios=ratios,threshold=.8,diagnostic_only=True)
def one_process(packet,repeat,identity):
 folder=packet/f'evidence/micro-B-{repeat}';w=read(folder/'window.json')
 require(w.get('repeat')==repeat and all(w.get(k) is True for k in ('passed','device_executed','drained','lease_released')),'clean fresh device window required')
 require(w['binary_sha256']==identity['binary_sha256'] and w['build_receipt_sha256']==identity['build_sha256'] and w['prerequisite_bindings']==identity,'wrong micro build or CPU evidence')
 verify(folder/'native',w['native_artifacts']);require(set(w['native_artifacts'])=={'receipt.json','checks.json','iterations.jsonl'},'missing native bindings')
 require(read(folder/'native/checks.json')['byte_exact_pairs']==100,'complete byte comparisons required')
 require(w['samples_sha256']==sha(folder/'samples.jsonl'),'changed stdout')
 require(read(folder/'native/receipt.json')==w['native_summary'],'native summary differs')
 r=analyze([json.loads(s) for s in (folder/'native/iterations.jsonl').read_text().splitlines()]);r['window_sha256']=sha(folder/'window.json');return r,w
def measured(packet=P):
 identity=prerequisites(packet);pairs=[one_process(packet,n,identity) for n in (1,2)];a,b=[w for _,w in pairs]
 ids=[(w['boot_id'],w['pid'],w['process_start_ticks']) for w in (a,b)];require(ids[0]!=ids[1] and a['finished_utc_ns']<=b['started_utc_ns'],'two sequential fresh native processes required')
 return dict(passed=True,qualified=['p122'] if all(r['qualified']==['p122'] for r,_ in pairs) else [],processes=[r for r,_ in pairs],identity=identity,gate_sha256=sha(P/'micro_gate.py'),diagnostic_only=True)
def evaluate(packet=P,repeat=None):
 prerequisites(packet)
 if not all((packet/f'evidence/micro-B-{n}/window.json').is_file() for n in (1,2)):return dict(passed=False,pending=True,qualified=[])
 row=measured(packet);(packet/'evidence/micro-qualification.json').write_text(json.dumps(row,indent=2)+'\n');return row
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--require-qualified',action='store_true');a=ap.parse_args()
 try:
  row=measured();require(row==read(P/'evidence/micro-qualification.json'),'stale qualification');require(row['qualified']==['p122'],'HC classes did not cut to <=0.8 in both processes/contexts/orders');print(json.dumps(row))
 except (OSError,KeyError,ValueError) as e:raise SystemExit('REFUSED: '+str(e))
