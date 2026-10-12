"""Summarize actual T1 receipts; never fill missing timing points."""
import argparse,json,statistics,math
from pathlib import Path

def summarize(root):
 rows=[]
 expected=set()
 for g in range(4):
  for sg in range(2):
   for local in range(2):
    for barrier in range(1 if g==0 else 2):
     for pointer in range(2):
      for n in (1,32,640,2560,6400,10240,25600):
       for parts in (1,2,4):expected.add(f'g{g}-sg{sg}-l{local}-b{barrier}-p{pointer}-n{n}-split{parts}-burst1')
  expected.add(f'g{g}-sg1-l0-b0-p0-n1-split1-burst1000')
 seen=set()
 for p in sorted(root.glob('g*-sg*-n*.json')):
  r=json.loads(p.read_text());rows.append(r)
  if r['class'] in seen or r['class']!=p.stem:raise ValueError('duplicate/misnamed row: '+str(p))
  seen.add(r['class'])
  identity=f"g{r['geometry']}-sg{int(r['subgroup32'])}-l{int(r['unused_local'])}-b{int(r['barrier'])}-p{int(r['parameter_pointer'])}-n{r['N']}-split{r['parts']}-burst{r['burst']}"
  if identity!=r['class']:raise ValueError('row identity disagrees with axes')
  for axis in ('gpu','wall'):
   v=r[axis+'_us'];r[axis+'_median_us']=statistics.median(v) if v else None;r[axis+'_p90_us']=sorted(v)[math.ceil(.9*len(v))-1] if v else None
   if r.get('passed') and (len(v)!=200 or not all(isinstance(x,(int,float)) and math.isfinite(x) and x>0 for x in v)):raise ValueError('incomplete timing: '+str(p))
 if seen!=expected:raise ValueError(f'incomplete launch matrix: missing={len(expected-seen)} extra={len(seen-expected)}')
 lines=['| N | geometry | SG32 | unused local | barrier | parameter pointer | launches | burst | GPU median / p90 us | wall median / p90 us |','|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 names={0:'range',1:'WG32 lane0',2:'WG32 all lanes',3:'WG256 all lanes'}
 by_name={r['class']:r for r in rows}
 for r in rows:
  for axis in ('gpu','wall'):
   value=r[axis+'_median_us'];r[axis+'_per_launch_us']=value/(r['parts']*r['burst']) if value is not None else None
   if r['burst']==1000 and r['passed']:
    base=by_name[f"g{r['geometry']}-sg1-l0-b0-p0-n1-split1-burst1"]
    r[axis+'_burst_per_launch_ratio']=r[axis+'_per_launch_us']/base[axis+'_median_us'] if base['passed'] else None

 for r in rows:
  if r['passed']:lines.append(f"| {r['N']} | {names[r['geometry']]} | {r['subgroup32']} | {r['unused_local']} | {r['barrier']} | {r['parameter_pointer']} | {r['parts']} | {r['burst']} | {r['gpu_median_us']:.4f} / {r['gpu_p90_us']:.4f} | {r['wall_median_us']:.4f} / {r['wall_p90_us']:.4f} |")
  else:lines.append(f"| {r['N']} | {names[r['geometry']]} | {r['subgroup32']} | {r['unused_local']} | {r['barrier']} | {r['parameter_pointer']} | {r['parts']} | {r['burst']} | FAILED | {r.get('error','unknown')} |")
 lines+=['','| Geometry | burst GPU us/launch | GPU ratio vs one | burst wall us/launch | wall ratio vs one |','|---|---:|---:|---:|---:|']
 for r in rows:
  if r['burst']==1000 and r['passed']:lines.append(f"| {names[r['geometry']]} | {r['gpu_per_launch_us']:.6f} | {r.get('gpu_burst_per_launch_ratio')} | {r['wall_per_launch_us']:.6f} | {r.get('wall_burst_per_launch_ratio')} |")
 rules=[];winners={}
 for n in (1,32,640,2560,6400,10240,25600):
  candidates=[r for r in rows if r['passed'] and r['N']==n and r['burst']==1]
  if candidates:
   best=min(candidates,key=lambda r:(r['gpu_median_us'],r['wall_median_us']));winners[str(n)]=best['class'];rules.append(f"N={n}: {best['class']} ({best['gpu_median_us']:.4f} us GPU median)")
 rule='The lowest measured GPU median for the exact BF16 elementwise operation was '+('; '.join(rules) if rules else 'not established')+'. This rule applies to these measured trivial independent elements; a kernel with reductions, dependencies, or a different body still requires its own byte and timing gate. Host-wall medians include submission and wait, GPU-event sums exclude launch gaps; burst rows separately test whether 1,000 consecutive submissions amortize host and event costs.'
 native_receipt=json.loads((root/'receipt.json').read_text()) if (root/'receipt.json').exists() else {}
 result=dict(schema='packet42.launch-floor.v1',rows=rows,winners=winners,rule=rule,device_measured=native_receipt.get('device_executed') is True,mock=native_receipt.get('mock',False))
 return result,'\n'.join(lines)+'\n\n'+rule+'\n'
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);v=a.parse_args();r,md=summarize(v.output)
 for name,body in [('launch-summary.json',json.dumps(r,indent=2)+'\n'),('launch-table.md',md)]:
  tmp=v.output/(name+'.tmp');tmp.write_text(body);tmp.replace(v.output/name)
 print(r['rule'])
