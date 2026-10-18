"""CPU source decision: two dimensions, >=0.5% over every matched B control."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];STAGE=ROOT/'experiments/own-xpu-runtime/stage2';P=STAGE/'packet111-record-bundle'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def probe(label,command):
 r=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
 result=dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,device_executed=False)
 raw=json.dumps(result,sort_keys=True).encode();path=O/'evidence'/('source-'+label+'-'+hashlib.sha256(raw).hexdigest()[:16]+'.json');save(path,result)
 if r.returncode:return dict(status='pending',receipt=str(path.relative_to(ROOT)),sha256=sha(path),reason=r.stderr[-1000:])
 return dict(status='complete',receipt=str(path.relative_to(ROOT)),sha256=sha(path),result=json.loads(r.stdout))
def threshold(candidate,controls):
 assert len(controls)>=2 and min(controls)>0
 return candidate/max(controls)>=1.005

def lane_a_loss(result,choice):
 rows=result.get('screens',result.get('views',[]))
 controls=[r['rate'] for r in rows if r['choice'] in ('control','production')]
 candidates=[r['rate'] for r in rows if r['choice']==choice]
 assert len(controls)>=2 and candidates,'A evidence lacks matched controls/candidate'
 return min(candidates)<max(controls)

def read_sources():
 head=probe('head-B',[sys.executable,'-B',str(STAGE/'packet106b-draft-split/compare.py'),'--lane','B'])
 fusion=probe('fusion-B',[sys.executable,'-B',str(STAGE/'packet109-other-fusion/compare.py'),str(STAGE/'packet109-other-fusion/evidence/p109-v5-B')])
 for key,row in (('target_head',head),('other_fusion',fusion)):
  row['eligible']=False
  if row['status']=='complete':
   if key=='target_head':
    bracket=row['result']['brackets'][0];rows=bracket['screens'];candidate=next(r for r in rows if r['choice']=='head-split');controls=[rows[0]['rate'],rows[-1]['rate']]
    row['ratio']=candidate['rate']/max(controls);row['eligible']=threshold(candidate['rate'],controls)
   else:
    result=row['result'];rows=result['views'];controls=[r['rate'] for r in rows if r['choice']=='control'];candidates=[r['rate'] for r in rows if r['choice']=='candidate']
    assert len(candidates)==2 and len(controls)==3 and result['all_13_exact']
    row['ratio']=min(candidates)/max(controls);row['eligible']=threshold(min(candidates),controls)
 # Independent A confirmation, if it has actually completed. Loss vetoes B.
 aroots=list((STAGE/'screen/v4-lanes/evidence').glob('p106b-*-A-confirm-2'))
 if any((r/'window.json').exists() for r in aroots):
  a=probe('head-A',[sys.executable,'-B',str(STAGE/'packet106b-draft-split/compare.py'),'--lane','A']);head['lane_A']=a
  if a['status']=='complete':
   if lane_a_loss(a['result'],'head-split'):head.update(eligible=False,veto='lane A loss')
 for path in sorted((STAGE/'packet109-other-fusion/evidence').glob('p109-v5-A*')):
  if not (path/'window.json').exists():continue
  a=probe('fusion-A',[sys.executable,'-B',str(STAGE/'packet109-other-fusion/compare.py'),str(path)])
  fusion.setdefault('lane_A_brackets',[]).append(a)
  if a['status']=='complete' and lane_a_loss(a['result'],'candidate'):fusion.update(eligible=False,veto='lane A loss')
 return {'target_head':head,'other_fusion':fusion}
def decide(sources):
 return dict(other_fusion='fused' if sources['other_fusion']['eligible'] else 'production',target_head='split' if sources['target_head']['eligible'] else 'production')
def main():
 sources=read_sources();base=json.loads((P/'fixed-base.json').read_text());control=dict(base,other_fusion='production',target_head='production');candidate=dict(base,**decide(sources))
 row=dict(schema='packet111.source-decision.v1',evidence_rule='identical-selection-v1',threshold_ratio=1.005,control=control,candidate=candidate,sources=sources,device_executed=False,extra_dimension_selected=candidate!=control)
 ident=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:16];(O/'decisions').mkdir(exist_ok=True);path=O/'decisions'/(ident+'.json');save(path,row);save(O/'decision.json',dict(path=str(path.relative_to(ROOT)),sha256=sha(path),identity=ident))
 print(json.dumps(dict(decision=ident,selected=decide(sources),ratios={k:v.get('ratio') for k,v in sources.items()},extra_dimension_selected=candidate!=control)),flush=True)
if __name__=='__main__':main()
