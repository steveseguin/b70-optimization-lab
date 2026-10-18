"""Real p106 Runtime transfer/service/merge on payload-backed CPU mock owners."""
import json,subprocess,shutil
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from compile_turn import turn
import full_shape
S=B/'runtime-mock'
def main():
 limits();full_shape.S=S;generated=full_shape.generate()
 f=S/'main.cpp';t=f.read_text()
 t=t.replace('struct Item{size_t bytes;ownrt::Memory memory;}', 'struct Item{size_t bytes;ownrt::Memory memory;bool backed;}')
 t=t.replace('if(m==ownrt::Memory::device){p=', 'if(m==ownrt::Memory::device&&n>24576){p=')
 t=t.replace('Item{n,m}', 'Item{n,m,m!=ownrt::Memory::device||n<=24576}')
 t=t.replace('if(m!=ownrt::Memory::device)::operator delete(p);', 'if(dry.at(uintptr_t(p)).backed)::operator delete(p);')
 t=t.replace('bounds(a,n);bounds(b,n);return marker(d);', 'bounds(a,n);bounds(b,n);auto da=std::prev(dry.upper_bound(uintptr_t(a))),db=std::prev(dry.upper_bound(uintptr_t(b)));if(da->second.backed&&db->second.backed)std::memcpy(a,b,n);return marker(d);')
 f.write_text(t)
 entry=r'''#include <cxxabi.h>
#define main unused_model_entry
#include "main.cpp"
#undef main
int main(int argc,char**argv){try{
 require(argc==3,"selection output");std::unique_ptr<Engine> es[2];std::unique_ptr<Weights> ws[2];std::unique_ptr<p106::Runtime> suffix;std::unique_ptr<mtp36::DraftRuntime> provider;p106::Runtime* rt[2]{};
 for(int r=0;r<2;++r){Options a;a.context=4096;a.cards=1;a.rank=r;a.draft_rank=1;a.target_split=0;a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=packet26::hash_file(a.selection);a.output=fs::path(argv[2])/std::to_string(r);fs::create_directories(a.output);a.plan=ROOT/"../suite-inputs-20261012/code-review/plan.tsv";a.draft_manifest=ROOT/"mtp-manifest.tsv";packet26::dispatch.load((ROOT/"dispatch-speed6.json").string());ws[r]=std::make_unique<Weights>(a);auto p=pipeline::split(plan(*ws[r],a),r,false,1,0);es[r]=std::make_unique<Engine>(*ws[r],a,p);es[r]->initialize();if(r==0){suffix=std::make_unique<p106::Runtime>(*es[r]);rt[r]=suffix.get();}else{provider=std::make_unique<mtp36::DraftRuntime>(*es[r]);rt[r]=provider->split_runtime.get();require(rt[r],"draft split runtime binding");}}
 auto pointer=[&](int r,Allocation id){return es[r]->dev(0).arena.row(id).pointer;};
 std::unique_ptr<p105::Runtime> target_rt[2];
 if(es[0]->split_head())for(int r=0;r<2;++r)target_rt[r]=std::make_unique<p105::Runtime>(*es[r]);
 p106::Mailbox box{};int callbacks=0;
 provider->configure_split(false,box,1,32,1);require(p106::load(box.request)==0,"miss dispatched suffix");
 provider->configure_split(true,box,1,32,1);provider->configure_split(false,box,1,32,1);

 for(int step=1;step<=2;++step){ // two consecutive hit services: speculative streams deliberately disagree.
  for(int r=0;r<2;++r){es[r]->a.output=fs::path(argv[2])/std::to_string(r)/std::to_string(step);fs::create_directories(es[r]->a.output);rt[r]->reset_trace();if(target_rt[r])target_rt[r]->reset_trace();}
  std::vector<uint8_t> verified(5120),speculative(20480,uint8_t(step==1?0x33:0xcc));for(size_t i=0;i<verified.size();++i)verified[i]=uint8_t(i*17+step);
  std::memcpy(pointer(1,rt[1]->hidden),verified.data(),verified.size());
  auto stream=es[0]->buffers[0].at("streams").id;std::memcpy(pointer(0,stream),speculative.data(),speculative.size());
  es[0]->history0=123+step;es[0]->history1=456+step;
  p106::Best a{step==1?1.f:3.f,100,0,0},b{2.f,int32_t(p106::prefix+7),0,0};
  std::memcpy(pointer(0,rt[0]->best),&b,16);std::memcpy(pointer(1,rt[1]->best),&a,16);
  rt[1]->export_hidden(box,step,step+31,step);
  require(p106::load(box.request)==uint32_t(step-1),"hidden published too soon");rt[1]->publish_hidden(box);
  uint32_t inactive=0;es[0]->upload(0,rt[0]->active,0,&inactive,4); // same effect as request reset
  rt[0]->service(box,step,step+31,step,[&]{++callbacks;});
  require(*static_cast<uint32_t*>(pointer(0,rt[0]->active))==1,"reset left suffix inactive");
  require(!std::memcmp(pointer(0,rt[0]->hidden),verified.data(),5120),"suffix used speculative hidden");
  require(!std::memcmp(pointer(0,stream),speculative.data(),20480)&&es[0]->history0==123+step&&es[0]->history1==456+step,"suffix mutated speculative state");
  rt[1]->merge_draft(box,step,step+31,step,[&]{++callbacks;});int32_t token;std::memcpy(&token,pointer(1,rt[1]->index),4);require(token==p106::merge(a,b).index,"merged token");
 }
 if(target_rt[0]){
  p105::Mailbox target_box{};
  auto& zero=*target_rt[0];auto& one=*target_rt[1];
  std::memset(pointer(1,one.hidden),0x5a,5120);
  p105::Best local{1.f,101,0,0},remote{2.f,int32_t(p105::prefix+3),0,0};
  std::memcpy(pointer(0,zero.best),&remote,16);std::memcpy(pointer(1,one.best),&local,16);
  uint32_t inactive=0;es[0]->upload(0,zero.active,0,&inactive,4);
  one.export_hidden(target_box,1,32,1);zero.service(target_box,1,32,1,[]{});
  require(*static_cast<uint32_t*>(pointer(0,zero.active))==1,"reset left target suffix inactive");
  one.merge_target(target_box,1,32,1,[]{});
  require(*static_cast<int32_t*>(pointer(1,one.index))==remote.index,"combined target suffix merge");
  require(p106::load(box.reply)==2,"target service changed draft mailbox");
 }
 int32_t before_bad=*static_cast<int32_t*>(pointer(1,rt[1]->index));box.best.error=1;
 bool bad=false;try{rt[1]->merge_draft(box,2,33,2,[]{});}catch(const std::exception&){bad=true;}
 require(bad&&*static_cast<int32_t*>(pointer(1,rt[1]->index))==before_bad,"nonfinite suffix published a proposal");
 bool stale=false;try{rt[0]->service(box,2,33,2,[]{});}catch(const std::exception&){stale=true;}require(stale,"duplicate accepted");
 bool wrong=false;box.position=999;p106::publish(box.request,3);try{rt[0]->service(box,3,34,3,[]{});}catch(const std::exception&){wrong=true;}require(wrong,"stale position accepted");
 bool cancelled=false;box.position=34;try{rt[0]->service(box,3,34,3,[]{throw std::runtime_error("cancel");});}catch(const std::exception&){cancelled=true;}require(cancelled&&p106::load(box.reply)==2,"cancel published");
 p106::publish(box.abort,1);bool aborted=false;try{rt[0]->service(box,3,34,3,[]{});}catch(const std::exception&){aborted=true;}require(aborted,"peer exit ignored");
 suffix.reset();provider.reset();for(int r=0;r<2;++r){target_rt[r].reset();es[r]->shutdown();es[r].reset();}
 for(int r=0;r<2;++r)for(int step=1;step<=2;++step)require(fs::file_size(fs::path(argv[2])/std::to_string(r)/std::to_string(step)/"p106-transfers.jsonl")>0,"request transfer trace missing");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"verified_draft_hidden_repeated_hits\":true,\"private_state_unchanged\":true,\"stale_duplicate_cancel_exit_refused\":true,\"callbacks\":"<<callbacks<<"}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
'''.replace('ROOT', 'fs::path('+json.dumps(str(P))+')')
 # No new hash implementation: pass the sealed selection digest explicitly.
 entry=entry.replace('packet26::hash_file(a.selection)', '[] (const fs::path& p){std::ifstream f(p);std::vector<uint8_t> t((std::istreambuf_iterator<char>(f)),{});return ::hash(t);}(a.selection)')
 (S/'entry.cpp').write_text(entry)
 cmds=json.loads((P/'engine-commands.json').read_text());base=next(r['command'] for r in cmds if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')];base=[x for x in base if not x.startswith('-O')]+['-O0','-I'+str(P)]
 commands=[[ *base,'-c',str(S/'entry.cpp'),'-o',str(S/'entry.o')]]
 link=list(next(r['command'] for r in cmds if r['name']=='gnu-host-link'));link=[x for x in link if not x.endswith('/entry-main.o') and not x.endswith('own-rt-iq3-entry.cpp.o')];link.insert(link.index('-o'),str(S/'entry.o'));link[link.index('-o')+1]=str(S/'fixture');commands.append(link)
 for i,cmd in enumerate(commands):
  with turn(),(S/f'build-{i}.log').open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 runs=[]
 for choice in ('head-split+draft-split',):
  dest=S/'scratch';cmd=[str(S/'fixture'),str(P/'selections'/choice/'selection.json'),str(dest)]
  r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
  assert r.returncode==0,r.stderr
  runs.append(dict(choice=choice,command=cmd,**json.loads(r.stdout)));shutil.rmtree(dest)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'runtime_mock.py',P/'p106_runtime.hpp',P/'p106_common.hpp',*generated,S/'fixture']}
 save(P/'evidence/runtime-mock.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,commands=commands))
 print('Actual Runtime on two CPU mocks: hit/miss verified hidden, private state, stale/duplicate/cancel/exit PASS',flush=True)
if __name__=='__main__':main()
