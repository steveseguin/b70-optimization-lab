"""Generate auditable packet29-derived harness and compile only; never execute it."""
import argparse,hashlib,json,os,re,resource,shlex,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent; B=P/'build'; OLD=P.parent/'packet29-merged'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(text,before,after):
 assert text.count(before)==1,(before,text.count(before))
 return text.replace(before,after)
def guarded(text):
 edits=[]
 for match in re.finditer(r'h\.parallel_for\(',text):
  start=text.index('[=]',match.end());body=text.index('{',start);depth=1;end=body+1
  while depth:
   depth+=(text[end]=='{')-(text[end]=='}');end+=1
  edits.extend([(start,'p28::checked('),(end,')')])
 for at,value in sorted(edits,reverse=True):text=text[:at]+value+text[at:]
 return text,len(edits)//2
def route_gate_source():
 source=(OLD/'round2_submit.cpp').read_text();start=source.index('struct SimpleArgs {');end=source.index('#ifdef OWN_RT_HOST_ONLY',start);core=source[start:end]
 candidate=(B/'p33_round2_submit.cpp').read_text();start=candidate.index('struct SimpleArgs {');end=candidate.index('#ifdef OWN_RT_HOST_ONLY',start);newcore=candidate[start:end]
 rank='for(int k=0;k<n&&rank<top;++k)rank+=a.scratch[k]>v||(a.scratch[k]==v&&k<j);'
 assert newcore==replace(core,rank,'if(n==512&&top==10)rank=int(p33::route_rank<512,10>(a.scratch,unsigned(j)));else '+rank)
 output=B/'route_gate_core.hpp';output.write_text('#pragma once\nnamespace p33_route_ref {\n'+core+'\n}\nnamespace p33_route_new {\n'+newcore+'\n}\n');return output
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--generate-only',action='store_true');args=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
 (B/'driver-tmp').mkdir(parents=True,exist_ok=True);os.environ['TMPDIR']=str(B/'driver-tmp')
 proof={'device_executed':False,'sources':{},'generated':{},'changes':{},'compile':[]}
 source=OLD/'gemv_timing.cpp';s=source.read_text();proof['sources'][str(source)]=sha(source)
 s='#include "'+str(P/'p33_submit.hpp')+'"\n#include "'+str(P/'p33_stop.hpp')+'"\n'+s
 s=replace(s,'constexpr auto& shapes=p28::shapes;','constexpr std::array shapes{p28::shapes[0],p28::shapes[1],p28::shapes[2],p28::shapes[3],p28::shapes[4],p28::shapes[8]};')
 start=s.index('  auto candidates=');end=s.index('\n  auto fp32=',start)
 s=s[:start]+'  auto candidates=s.type==iq3::Type::IQ4_NL?std::vector<std::string>{"p33.down.bank","p33.down.select"}:s.paired?std::vector<std::string>{"p33.gate.restrict"}:std::vector<std::string>{"p33.dense.segment"};'+s[end:]
 before='(selected.starts_with("p28.")?p28::submit(r.device,current,selected,s.paired,v):selected.starts_with("p29.")?p29::submit(r.device,current,selected,s.paired,v):packet26::p25bridge::submit(r.device,current,selected,s.paired,v,fp32))'
 s=replace(s,before,'p33::submit(r.device,current,selected,s.paired,v)')
 assert '216u' in s and 'iteration>=8&&iteration<208' in s and 'copies=heavy?8:1' in s
 s=s.replace('try{fixture_validation::inject_failure','try{p33::check_stop();fixture_validation::inject_failure')
 s=s.replace('catch(const std::exception& e){if(!timing','catch(const std::exception& e){if(p33::stop_requested)throw;if(!timing')
 out=B/'p33_gemv_timing.cpp';out.write_text(s);proof['generated'][str(out)]=sha(out)
 proof['changes']['gemv']=['prepend p33 submit declaration','restrict unchanged shape rows to expsgate IQ2/IQ3, expsdown IQ4, gdn.qkv Q6/Q8','replace candidate list with four packet33 IDs','replace only candidate submit expression; R5 integrated::experts/dense unchanged','216 iterations, 8 preflight+200 measured+8 postflight, heavy buffers8 unchanged']
 source=OLD/'round2_submit.cpp';s=source.read_text();proof['sources'][str(source)]=sha(source)
 s='#include "'+str(P/'p33_submit.hpp')+'"\n#include "'+str(P/'candidates.hpp')+'"\n'+s
 s=replace(s,'namespace round2 {','namespace p33r2 {\nusing namespace round2;')
 rank='for(int k=0;k<n&&rank<top;++k)rank+=a.scratch[k]>v||(a.scratch[k]==v&&k<j);'
 s=replace(s,rank,'if(n==512&&top==10)rank=int(p33::route_rank<512,10>(a.scratch,unsigned(j)));else '+rank)
 call='group<Code,Stage>(shape,a,int(it.get_group_linear_id()),global,Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});'
 replacement='if(shape.capacity==128&&shape.budget==2048&&shape.tokens==1)p33::qsa_group<Code,Stage,128,2048,1>(shape,a,int(it.get_group_linear_id()),global,Team{it,x.get_multi_ptr<sycl::access::decorated::no>().get()});else '+call
 s=replace(s,call,replacement)
 # Iteration 2: select fixed shape on the host. The first spelling placed both
 # paths inside each device kernel and inflated the generated code.
 s=s.replace('template<ng::Op Code,int Stage> struct Kernel', 'template<ng::Op Code,int Stage,bool Fixed=false> struct Kernel')
 s=replace(s,'if(shape.capacity==128&&shape.budget==2048&&shape.tokens==1)p33::qsa_group', 'if constexpr(Fixed)p33::qsa_group')
 s=replace(s,'Kernel<Code,0> first(s);auto e=d.compute(first,a,deps);',
   'auto first_issue=[&]<bool F>(){Kernel<Code,0,F> first(s);return d.compute(first,a,deps);};auto e=(Code!=ng::gdn&&s.capacity==128&&s.budget==2048&&s.tokens==1)?first_issue.template operator()<true>():first_issue.template operator()<false>();')
 s,count=guarded(s);assert count==3,count
 out=B/'p33_round2_submit.cpp';out.write_text(s);proof['generated'][str(out)]=sha(out)
 proof['changes']['round2']=['rename own namespace to p33r2, import unchanged round2 headers','stage1 route: p33 route_rank for512/top10 only, generic fallback retained','fixed QSA shape128/2048/1 delegates unchanged arithmetic body; generic fallback retained','wrap all3 parallel_for captures with p28::checked (<=1024 bytes)']
 entries=json.loads((OLD/'build/device/compile_commands.json').read_text());example=next(r for r in entries if r['file'].endswith('/gemv_timing.cpp'))
 command=shlex.split(example['command']);base=command[:command.index('-o')]+['-I'+str(P)]
 for source in [P/'p33_submit.cpp',B/'p33_gemv_timing.cpp',B/'p33_round2_submit.cpp']:
  obj=B/(source.stem+'.o');cmd=base+['-fsycl-dump-device-code='+str(B),'-c',str(source),'-o',str(obj)]
  row={'source':str(source),'source_sha256':sha(source),'command':cmd,'object':str(obj)}
  if not args.generate_only:
   result=subprocess.run(cmd,capture_output=True,text=True);log=B/(source.stem+'-compile.log');log.write_text(result.stdout+result.stderr);row.update(returncode=result.returncode,log=str(log))
   proof['compile'].append(row)
   if result.returncode:
    (P/'generation-proof.json').write_text(json.dumps(proof,indent=2)+'\n');raise RuntimeError(result.stderr)
   row['object_sha256']=sha(obj)
  else:proof['compile'].append(row)
 (P/'generation-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps({'generated':list(proof['generated']),'objects':[r['object'] for r in proof['compile']],'device_executed':False}))
if __name__=='__main__':main()
