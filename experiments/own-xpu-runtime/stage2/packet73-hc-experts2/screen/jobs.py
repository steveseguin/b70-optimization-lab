"""Fixed A grid and an evidence-selected B sandwich; CPU planning only by default."""
from pathlib import Path
from common import HERE,require
QUICK=HERE;P=HERE.parent
CANDIDATES=('hc-wide','experts2-a','experts2-b','combined')
ORDERS={'A':('production',*CANDIDATES,'production'),'B':('production','best-of-lane-A','production')}
def jobs(path,lane,best=None):
 rows=[]
 for line in Path(path).read_text().splitlines():
  if not line.strip() or line.startswith('#'):continue
  fields=line.split('|');require(len(fields)==6,'six job fields required')
  out,lineage,seal,binary,dispatch,placement=fields;v=Path(lineage).resolve();choice=v.name
  require(v==P/'selections'/choice and choice in ORDERS[lane],'foreign selection')
  require(Path(seal).resolve()==v/'screen-seal.json' and Path(binary).absolute()==v/'build/device/own-rt-iq3' and Path(dispatch).resolve()==v/'dispatch-speed6.json' and placement=='1','job identity changed')
  require(Path(out).name==out and out.startswith('p73-quick-'+lane+'-'),'invalid output')
  rows.append(dict(out=out,choice=choice,lineage=lineage,seal=seal,binary=binary,dispatch=dispatch,placement=placement))
 require(tuple(r['choice'] for r in rows)==ORDERS[lane],'fixed lane order required')
 require(len({r['out'] for r in rows})==len(rows),'duplicate output')
 if lane=='B':
  if best is None:
   from winner import verify_lane_a
   best=verify_lane_a()['choice']
  require(best in CANDIDATES,'unregistered winner')
  row=rows[1];v=P/'selections'/best
  row.update(choice=best,lineage=str(v),seal=str(v/'screen-seal.json'),binary=str(v/'build/device/own-rt-iq3'),dispatch=str(v/'dispatch-speed6.json'))
 return rows
def command(row,lane,review=None,plan=False):
 cmd=['/usr/bin/python3','-B',str(HERE/'screen.py'),'--profile','tp2','--lane',lane,'--timing','token','--placement','1']
 for k in ('lineage','seal','binary','dispatch'):cmd+=['--'+k,row[k]]
 cmd+=['--output',str(HERE/'evidence'/row['out'])]
 return cmd+(['--plan'] if plan else ['--fault-review',str(review),'--authorized-device-window'])
