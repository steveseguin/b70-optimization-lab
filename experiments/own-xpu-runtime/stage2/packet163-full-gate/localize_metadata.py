import json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent
for n in('one-card','two-card'):
 p=P/n
 moves=[('lineage-source','lineage'),('oracle128','lineage/oracle128'),('build-inputs.json','lineage/build-inputs.json'),('evidence/parent-summary.json','lineage/parent-summary.json'),('evidence/parent-window.json','lineage/parent-window.json'),('evidence/parent-requests','lineage/parent-requests')]
 for a,b in moves:
  src=p/a;dest=p/b
  if src.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(src,dest)
 cp=json.loads((p/'copy-manifest.json').read_text());files={}
 for k,v in cp['files'].items():
  for a,b in moves:
   if k==a or k.startswith(a+'/'):k=b+k[len(a):];break
  files[k]=v
 cp['files']=files;(p/'copy-manifest.json').write_text(json.dumps(cp,indent=2)+'\n')
 for f in(p/'fault_review.py',p/'worker.py'):
  text=f.read_text().replace('lineage-source/window_driver.py','lineage/window_driver.py').replace("HERE/'oracle128", "HERE/'lineage/oracle128")
  text=text.replace('exec_limits.install()','')
  text=text.replace('child=subprocess.Popen(cmd,','exec_limits.check();child=subprocess.Popen(cmd,')
  text=text.replace('pipeline.Transport.__init__(transport,args,','exec_limits.check();pipeline.Transport.__init__(transport,args,')
  f.write_text(text)
