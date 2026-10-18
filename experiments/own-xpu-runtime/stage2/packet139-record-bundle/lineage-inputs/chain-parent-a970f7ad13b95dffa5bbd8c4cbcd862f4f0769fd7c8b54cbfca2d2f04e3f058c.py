"""Actual plan/group construction, metadata only; no arithmetic or weights."""
import hashlib,json,os,re,subprocess
from pathlib import Path
import plan_group_gate as group
P=Path(__file__).resolve().parent;E=P/'evidence/speed1';B=P/'build/speed1-plan'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def instrument(code):
 needle='Probe e(w,a,std::move(p));std::cout'
 assert code.count(needle)==1
 return code.replace(needle,'''Probe e(w,a,std::move(p));
 size_t ffns=0,shared=0;std::map<int,size_t> tags;
 for(const auto& [site,g]:e.small_groups)if(g.name.starts_with("small.ffn"))++ffns;
 for(const auto&site:e.p.launches)if(p39::tagged(site)){++tags[int(p39::kind(site))];if(p39::kind(site)==p39::Kind::shared_act)++shared;}
 std::cerr<<"ffn="<<ffns<<" shared="<<shared;
 for(auto[k,v]:tags)std::cerr<<" tag"<<k<<"="<<v;std::cerr<<"\\n";
 std::cout''')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 E.mkdir(exist_ok=True);B.mkdir(exist_ok=True);group.B=B;group.E=E
 group.generate('after',instrument)
 rows=[]
 for context in (4096,32768):
  for dr in (0,1):
   for kind,rank in [('target',0),('target',1),('KD',1),('draft',dr)]:
    for dispatch in ('dr0','dr1','forced'):
     path=P/f'evidence/fix6/dispatch-{dispatch}.json'
     cmd=[str(B/'after'),kind,str(context),str(dr),str(rank),str(path)]
     run=subprocess.run(cmd,text=True,capture_output=True);result=json.loads(run.stdout)
     assert run.returncode==0 and result['passed'],run.stderr+run.stdout
     counts={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',run.stderr)}
     if kind!='draft':
      layers=(22 if dr==0 else 24) if rank==0 else (26 if dr==0 and kind!='KD' else 24)
      assert counts['ffn']==layers and counts['shared']==0,(kind,dr,rank,counts)
     rows.append(dict(plan=kind,context=context,draft_rank=dr,rank=rank,dispatch=dispatch,
                      dispatch_sha256=sha(path),result=result,group_census=counts))
 for c in (4096,32768):
  for dr in (0,1):
   for dispatch in ('dr0','dr1','forced'):
    target=[r for r in rows if (r['context'],r['draft_rank'],r['dispatch'],r['plan'])==(c,dr,dispatch,'target')]
    assert sum(r['group_census']['ffn'] for r in target)==48
 sources=('speed1_plan_gate.py','plan_group_gate.py','main.cpp','rank.hpp','mtp.hpp','p39_plan.hpp','small_gemv.cpp','small_gemv.hpp')
 report=dict(passed=True,device_executed=False,weight_bytes_read=0,plan_dispatch_rows=len(rows),
  target_ffn_groups=48,commands_per_tuple_before=6,commands_per_tuple_after=2,
  removed_target_commands=192,command_count_scope='48 restored groups times the retained six-to-two command recipes; no model execution',
  sources_sha256={n:sha(P/n) for n in sources},metadata_sha256=sha(P/'build/input/plan.tsv'),
  binary_sha256=sha(B/'after'),generated_sha256=sha(B/'after.cpp'),rows=rows)
 (P/'speed1-plan-gates.json').write_text(json.dumps(report,indent=2)+'\n')
 (E/'plan-sweep.json').write_text(json.dumps(rows,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ('rows','sources_sha256')}))
if __name__=='__main__':main()
