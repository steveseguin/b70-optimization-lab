"""Whole miniature two-rank target/draft outputs against frozen packet124c."""
import json,shutil
from build131 import P,ROOT,B,BASE,sha,save,cpu_main,limits
def main():
 import mini_gate as g
 g.BASE=BASE;g.selection=lambda x:x
 def miniature(row):
  for key in ('route','recurrence','hc','experts','hc_gate','hc_norm','head','other_fusion'):row['choices'][key]='production'
  row['choices']['route']='route-exp32-rank4';row['choices']['recurrence']='rows4-shared'
  return row
 expected,row=g.run_one('parent124c',BASE/'build/gnu-host/own-rt-iq3',1,0,miniature(json.loads((P/'selections/control/selection.json').read_text())));rows=[row]
 for view in ('control','candidate'):
  selection=miniature(json.loads((P/'selections'/view/'selection.json').read_text()))
  for repeat in (1,2):
   actual,row=g.run_one(f'{view}-{repeat}',B/'gnu-host/own-rt-iq3',1,0,selection)
   assert actual==expected,'target/draft bytes differ from frozen packet124c'
   rows.append(row);print(view,repeat,'24 tokens, 96 layer outputs and draft bytes MATCH',flush=True)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'mini131.py',P/'mini_gate.py',P/'pipeline.py',BASE/'build/gnu-host/own-rt-iq3',B/'gnu-host/own-rt-iq3',*(P/'selections'/v/'selection.json' for v in ('control','candidate'))]}
 save(P/'evidence/mini131.json',dict(passed=True,device_executed=False,runs=rows,sources=sources))
 shutil.rmtree(g.MINI);limits()
if __name__=='__main__':cpu_main();main()
