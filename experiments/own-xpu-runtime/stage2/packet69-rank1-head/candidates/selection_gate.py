"""Exercise linked production parser only; never construct a model or device."""
import json,subprocess,resource
from build_engine import P,ROOT,BASE,limits,sha,save
from selections import CHOICES,selection

def main():
 limits();resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 src=P/'build/selection-entry.cpp';src.write_text('''#include "p49d_submit.hpp"
#include <iostream>
int packet26_model_entry(int argc,char**argv){try{p49d::Selection s;s.load(argv[1]);std::cout<<s.choices.at("target_head")<<" "<<s.choices.at("draft_head")<<" "<<s.draft.at("qsa_attention")<<"\\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<"\\n";return 2;}}
''')
 prior=json.loads((P/'engine-commands.json').read_text());base=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
 obj=P/'build/selection-entry.o';binary=P/'build/selection-parser'
 cmd=[*base,'-I'+str(P),'-o',str(obj),'-c',str(src)]
 with (P/'evidence/selection-compile.log').open('w') as log:subprocess.run(cmd,check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link[link.index('-o')+1]=str(binary)
 link=[str(obj) if x==str(P/'build/gnu-host/entry-main.o') else x for x in link]
 with (P/'evidence/selection-link.log').open('w') as log:subprocess.run(link,check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 rows=[]
 for choice in CHOICES:
  path=P/'selections'/choice/'selection.json';out=subprocess.run([str(binary),str(path)],capture_output=True,text=True,stdin=subprocess.DEVNULL,check=True)
  s=selection(choice);assert out.stdout.strip()==' '.join([s['choices']['target_head'],s['choices']['draft_head'],s['draft']['qsa_attention']])
  rows.append(dict(choice=choice,sha256=sha(path),parsed=out.stdout.strip()))
 for mode in ('unknown','target_change','missing','bad_fusion'):
  s=selection('production')
  if mode=='unknown':s['choices']['target_head']='made-up'
  if mode=='target_change':s['choices']['recurrence']='production'
  if mode=='missing':del s['choices']['draft_head']
  if mode=='bad_fusion':s['draft']['fuse_hc_a_mix']='packet59'
  path=P/'build'/('invalid-'+mode+'.json');save(path,s)
  result=subprocess.run([str(binary),str(path)],capture_output=True,text=True,stdin=subprocess.DEVNULL);assert result.returncode==2,(mode,result)
 save(P/'evidence/selection-gate.json',dict(passed=True,device_executed=False,cpu_model_executed=False,accepted=rows,rejected=['unknown','target_change','missing','bad_fusion'],sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('selection_gate.py','selections.py','p49d_submit.cpp','p49d_submit.hpp','p59c_select.hpp','main.cpp','mtp.hpp')}))
 print('PASS: seven linked selections and four refusals; no model')
if __name__=='__main__':main()
