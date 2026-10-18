"""Fixed packet72 screens; lane B is gated by completed lane-A evidence."""
from pathlib import Path
from common import HERE,require
QUICK=HERE;P=HERE.parent
ORDERS={'A':('production','attention-out','combined','production'),
        'B':('production','attention-out','production')}
def jobs(path,lane):
 rows=[]
 for line in Path(path).read_text().splitlines():
  if not line.strip() or line.startswith('#'):continue
  fields=line.split('|');require(len(fields)==6,'six job fields required')
  out,lineage,seal,binary,dispatch,placement=fields;v=Path(lineage).resolve();choice=v.name
  require(v==P/'selections'/choice and choice in ORDERS[lane],'foreign selection')
  require(Path(seal).resolve()==v/'screen-seal.json' and Path(binary).absolute()==v/'build/device/own-rt-iq3' and Path(dispatch).resolve()==v/'dispatch-speed6.json' and placement=='1','job identity changed')
  require(Path(out).name==out and out.startswith('p72-quick-'+lane+'-'),'invalid output')
  rows.append(dict(out=out,choice=choice,lineage=lineage,seal=seal,binary=binary,dispatch=dispatch,placement=placement))
 require(tuple(r['choice'] for r in rows)==ORDERS[lane],'fixed lane order required')
 require(len({r['out'] for r in rows})==len(rows),'duplicate output')
 return rows
def command(row,lane,review=None,plan=False):
 cmd=['/usr/bin/python3','-B',str(HERE/'screen.py'),'--profile','tp2','--lane',lane,'--timing','token','--placement','1']
 for k in ('lineage','seal','binary','dispatch'):cmd+=['--'+k,row[k]]
 cmd+=['--output',str(HERE/'evidence'/row['out'])]
 return cmd+(['--plan'] if plan else ['--fault-review',str(review),'--authorized-device-window'])
