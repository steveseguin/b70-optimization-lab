"""Run real production initialization/capture/allocation with payload-only mocks.
The generated test source changes no production file or arithmetic kernel.
Device extents are numerical address tokens, never mappings or model payloads.
"""
import json,subprocess,gzip
from compile_turn import turn
import os,hashlib
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices
S=B/'full-shape'
def replace(t,a,b):
 assert a in t,a
 return t.replace(a,b)
def body(t,marker,value):
 start=t.index('{',t.index(marker));depth=1;i=start+1
 while depth:
  if t[i]=='{':depth+=1
  if t[i]=='}':depth-=1
  i+=1
 return t[:start+1]+value+t[i-1:]
def generate():
 S.mkdir(exist_ok=True)
 mirror=B/'checked'/P.relative_to(ROOT)
 t=(mirror/'main.cpp').read_text();m=(mirror/'mtp.hpp').read_text()
 start=t.index('class Host final');end=t.index('\n#endif',start)
 t=t[:start]+r'''static std::map<std::string,unsigned> p80_operations;
class Host final : public packet18::LifetimeMock, public ownrt::OrderedQueue {
 struct Item{size_t bytes;ownrt::Memory memory;};std::map<uintptr_t,Item> dry;
 uintptr_t next=0x100000000000ULL;
 void bounds(const void*p,size_t n){auto x=uintptr_t(p);auto i=dry.upper_bound(x);require(i!=dry.begin(),"mock unknown pointer");--i;require(x-i->first<=i->second.bytes&&n<=i->second.bytes-(x-i->first),"mock copy extent");}
public:
 bool ordered_prefix_complete(ownrt::Event e)override{return complete(e);}
 void* allocate(size_t n,ownrt::Memory m)override{void*p;if(m==ownrt::Memory::device){p=reinterpret_cast<void*>(next);next+=((n+4095)&~size_t(4095))+4096;}else p=::operator new(n);dry.emplace(uintptr_t(p),Item{n,m});return p;}
 void release(void*p,ownrt::Memory m)override{require(dry.at(uintptr_t(p)).memory==m,"mock memory");if(m!=ownrt::Memory::device)::operator delete(p);dry.erase(uintptr_t(p));}
 ownrt::Event copy(void*a,const void*b,size_t n,std::span<const ownrt::Event>d)override{bounds(a,n);bounds(b,n);return marker(d);}
 ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event>d)override{return marker(d);}
 std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation> op,std::span<void*const>)override{std::string name=typeid(*op).name();int status=0;char*dem=abi::__cxa_demangle(name.c_str(),nullptr,nullptr,&status);if(dem){name=dem;std::free(dem);}++p80_operations[name];return [this]{return marker({});};}
 void close_queue()override{require(dry.empty(),"mock allocations remain");LifetimeMock::close_queue();}
};'''+t[end:]
 t=body(t,'Weights(const Options &a)', '\n directory=flash::directory_from_loader(iq3::read_plan(a.plan));\n')
 t=body(t,'std::vector<uint8_t> read(const std::string &name', '\n throw std::runtime_error("mock must never read model payload");\n')
 t=body(t,'std::vector<int64_t> metadata()', '\n std::vector<int64_t> v{3,5,7};v.insert(v.end(),16,17);for(int i=0;i<16;++i)v.push_back(17*i);return v;\n')
 # Size, dispatch and actual allocation are retained; only upload/expansion is mocked.
 t=replace(t,'    weights[c][name] = id;', '    weights[c][name] = id; return; // test-only payload elision')
 t=replace(t,'#include '+json.dumps(str(mirror/'mtp.hpp')),'#include '+json.dumps(str(S/'mtp.hpp')))
 m=replace(m,'mutable_ids.erase(w.id);','mutable_ids.erase(w.id);weights[name]=w;return; // test-only payload elision\n')
 m=replace(m,'auto raw=e.w.read("output.weight",row*rb,n*rb);if(arithmetic::is_expanded(head_variant))raw=iq3::expanded::expand(hw.type,raw.data(),raw.size(),hw.cols);','std::vector<uint8_t> raw(n*er);')
 m=replace(m,'auto source=e.w.read("output.weight",row*rb,n*rb);auto raw=p83::quantize(hw.type,source.data(),n,hw.cols);','std::vector<uint8_t> raw(n*er);')
 m=body(m,'if(store){require(store->reads.size()', '')
 (S/'mtp.hpp').write_text(m)
 (S/'main.cpp').write_text(t)
 for leaf in ('rope.bf16','mtp-manifest.tsv'):
  if not (S/leaf).exists():(S/leaf).symlink_to(P/leaf)
 entry=r'''#include <cxxabi.h>
#define main packet75_unexecuted_model_entry
#include "main.cpp"
#undef main
int main(int argc,char**argv){std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;std::function<void()> restore=[]{};try{
 require(argc==8,"view hash rank output negative draft_rank split");Options a;a.context=4096;a.cards=1;a.card=0;a.rank=std::stoi(argv[3]);a.draft_rank=std::stoi(argv[6]);a.target_split=std::stoi(argv[7]);a.mtp=true;a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[4];fs::create_directories(a.output);
 a.plan=PACKET_ROOT/"../suite-inputs-20261012/code-review/plan.tsv";a.draft_manifest=PACKET_ROOT/"mtp-manifest.tsv";
 packet26::dispatch.load((PACKET_ROOT/"dispatch-speed6.json").string());Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,false,a.draft_rank,a.target_split);
 require(arithmetic::row_bytes(iq3::Type::Q6_K,2560,6)==3380,"real expanded Q6 head stride");
 const std::string negative=argv[5];
 if(negative=="serial")a.nongemv="serial";
 if(negative=="gemv")a.gemv="r4";
 if(negative=="streaming")a.memory="layer-streaming";
 if(negative=="draft-rank")a.draft_rank=0;
 if(negative=="split")a.target_split=23;
 if(negative=="context")a.context=256;
 if(negative=="legacy")a.legacy=true;
 e=std::make_unique<Engine>(w,a,p);e->initialize();
 write_plan(a.output/"native-plan.json",p,w,a.cards,a);
 if(negative!="positive"){
  const bool expert=e->sealed_selection.choices.at("experts")=="exp-halfcache";
  const std::string suffix=expert?".ffn_gate_exps.weight":".hc_attn_up.weight";
  auto found=std::find_if(e->weights[0].begin(),e->weights[0].end(),[&](const auto&v){return v.first.ends_with(suffix);});require(found!=e->weights[0].end(),"negative weight missing");
  auto &r=const_cast<std::remove_const_t<std::remove_reference_t<decltype(e->dev(0).arena.row(found->second))>>&>(e->dev(0).arena.row(found->second));
  auto saved=r;auto id=found->second;restore=[&,id,saved]{auto &row=const_cast<std::remove_const_t<std::remove_reference_t<decltype(e->dev(0).arena.row(id))>>&>(e->dev(0).arena.row(id));row=saved;};
  if(negative=="short")--r.bytes;else if(negative=="misaligned")r.pointer=reinterpret_cast<void*>(uintptr_t(r.pointer)+2);else throw std::invalid_argument("negative mode");
 }
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 {pipeline::SpeculativeImage image(*e);if(a.rank==a.draft_rank)draft=std::make_unique<mtp36::DraftRuntime>(*e);
 auto count=[](const std::string& key){unsigned n=0;for(const auto&[name,value]:p80_operations)if(name.find(key)!=std::string::npos)n+=value;return n;};
 const auto& choice=e->sealed_selection.choices;
 require(count("p82rec::Kernel<true>")>0,"rec-parallel selection consumer");
 const bool expert=choice.at("experts")=="exp-halfcache",hc=choice.at("hc_gate")=="hc-weightcache";
 require((count("p90exp::Kernel<")>0)==expert,"cached expert selection consumer");
 require((count("p65::Kernel<(iq3::Type)22, 2560u, 64u, false, true, 0u>")>0)==!expert,"control expert consumer");
 require(count("p65::Kernel<(iq3::Type)20, 640u, 64u, false, true, 0u>")>0,"unchanged down expert consumer");
 require((count("p60::Kernel<2, true, false, true>")>0)==hc,"cached HC selection consumer");
 require((count("p60::Kernel<2, true, false, false>")>0)==!hc,"HC wide consumer");
 require(count("p78route::Kernel")==0&&count("p60::Kernel<0, false, true, false>")==0,"production route/norm");
 unsigned transformed=0;
 for(const auto&[name,id]:e->weights[0]){
  const auto&r=e->dev(0).arena.row(id);
  if(e->p90_expert_weight(name)){require(r.bytes==size_t(512)*640*840,"cached expert extent is real 840-byte stride");++transformed;}
  if(e->p90_hc_weight(name)){require(r.bytes==size_t(10240)*1280,"cached HC extent is real 1280-byte stride");++transformed;}
 }
 require(transformed==(expert?(a.rank==0?46u:48u):hc?48u:0u),"transformed target allocation count: "+std::to_string(transformed));
 std::ofstream selected(a.output/"selected-operations.txt");for(const auto&[name,value]:p80_operations)selected<<name<<" "<<value<<"\n";selected.close();
 require(e->ordered_retirement==(a.rank==1&&choice.at("host_retire")=="ordered"),"host retirement selection consumer");
 save(a.output/"census.json",e->dev(0).arena.census());save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"rank\":"+std::to_string(a.rank)+",\"postload_device_bytes\":"+std::to_string(e->owned_bytes[0])+",\"expanded_head_stride\":3380}");draft.reset();}
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';restore();draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
'''
 entry=entry.replace('PACKET_ROOT','fs::path('+json.dumps(str(P))+')')
 # Arena record name is discovered from the actual API, not duplicated.
 entry=entry.replace('auto &r=const_cast<ownrt::AllocationRecord&>(e->dev(0).arena.row(id));r.bytes-=2100;', 'auto &r=const_cast<std::remove_const_t<std::remove_reference_t<decltype(e->dev(0).arena.row(id))>>&>(e->dev(0).arena.row(id));r.bytes-=2100;')
 (S/'entry.cpp').write_text(entry)
 return [S/'main.cpp',S/'mtp.hpp',S/'entry.cpp']
def main():
 limits();generated=generate();cmds=json.loads((P/'engine-commands.json').read_text());base=next(r['command'] for r in cmds if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
 base=[x for x in base if not x.startswith('-O')]+['-O0','-I'+str(P)]
 command=[*base,'-c',str(S/'entry.cpp'),'-o',str(S/'entry.o')]
 with turn(), (S/'compile.log').open('w') as f:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
 link=list(next(r['command'] for r in cmds if r['name']=='gnu-host-link'))
 link=[x for x in link if not x.endswith('/entry-main.o') and not x.endswith('own-rt-iq3-entry.cpp.o')]
 link.insert(link.index('-o'),str(S/'entry.o'));link[link.index('-o')+1]=str(S/'fixture')
 with turn(), (S/'link.log').open('w') as f:subprocess.run(link,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
 report=dict(passed=False,device_executed=False,model_payload_read=False,runs=[],sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'main.cpp',P/'mtp.hpp',P/'rank.hpp',P/'full_shape.py',*generated]},commands=[command,link])
 for name,v in views().items():
  sel=json.loads((P/'selection.json').read_text());sel['choices']=choices(*v);path=S/(name+'.json');save(path,sel)
  for rank in (0,1):
   dest=S/name/str(rank);dest.mkdir(parents=True,exist_ok=True)
   cmd=[str(S/'fixture'),str(path),sha(path),str(rank),str(dest),'positive','1','0']
   with (dest/'run.log').open('w') as f:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=120)
   if r.returncode:raise ValueError('full shape failed '+str(dest))
   consumers=[line for line in (dest/'selected-operations.txt').read_text().splitlines() if line.startswith(('p49drec::','p82rec::','p65::','p90exp::','p60::'))]
   plan_archive=P/'evidence'/(name+'-'+str(rank)+'-native-plan.json.gz');plan_archive.write_bytes(gzip.compress((dest/'native-plan.json').read_bytes(),mtime=0))
   census=P/'evidence'/(name+'-'+str(rank)+'-census.json.gz');census.write_bytes(gzip.compress((dest/'census.json').read_bytes(),mtime=0))
   actual=json.loads((dest/'census.json').read_text());reported=json.loads((dest/'native-plan.json').read_text())
   weight_rows={r['label'].split('weight:',1)[1]:r['bytes'] for r in actual['allocations'] if r['live'] and r['memory']=='device' and r['label'].startswith('card0:weight:') and r['label'].split('weight:',1)[1].startswith('blk.')}
   planned={r['name']:r['stored_bytes'] for r in reported['tensor_owners']}
   for key,value in weight_rows.items():assert planned[key]==value,(name,rank,key,planned[key],value)
   report['runs'].append(dict(native_plan=str(plan_archive.relative_to(ROOT)),native_plan_sha256=sha(plan_archive),native_plan_weights_verified=len(weight_rows),census=str(census.relative_to(ROOT)),census_sha256=sha(census),view=name,selection_key_consumers_verified=True,selected_operations=consumers,selected_operations_sha256=sha(dest/'selected-operations.txt'),**json.loads((dest/'result.json').read_text())))
   print(name,rank,'PASS',flush=True)
 negatives=[]
 for name in views():
  sel=json.loads((P/'selection.json').read_text());sel['choices']=choices(name);path=S/(name+'.json');save(path,sel)
  for rank in (0,1):
   for kind in ('short','misaligned'):
    dest=S/(name+'-'+str(rank)+'-'+kind);dest.mkdir(exist_ok=True)
    r=subprocess.run([str(S/'fixture'),str(path),sha(path),str(rank),str(dest),kind,'1','0'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    log=P/'evidence'/(dest.name+'.log');log.write_text(r.stdout+r.stderr)
    expected='p39 allocation extent' if name=='exp-halfcache' and kind=='short' else 'p28 extent/alignment' if name=='exp-halfcache' else 'packet60 lifetime/extent/alignment'
    assert r.returncode!=0 and expected in r.stderr,(name,rank,kind,r.stderr)
    negatives.append(dict(view=name,rank=rank,mutation=kind,refusal=expected,passed=True,log_sha256=sha(log)))
 for case in ('missing-experts','unknown-experts','missing-hc','extra-key','unknown-gate'):
  sel=json.loads((P/'selection.json').read_text());sel['choices']=choices('exp-halfcache')
  if case=='missing-experts':del sel['choices']['experts']
  if case=='unknown-experts':sel['choices']['experts']='bogus'
  if case=='missing-hc':del sel['choices']['hc_gate']
  if case=='extra-key':sel['choices']['new_option']='production'
  if case=='unknown-gate':sel['choices']['hc_gate']='bogus'
  path=S/(case+'.json');save(path,sel);out=S/case;out.mkdir(exist_ok=True)
  r=subprocess.run([str(S/'fixture'),str(path),sha(path),'1',str(out),'positive','1','0'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
  (P/'evidence'/(case+'.log')).write_text(r.stdout+r.stderr)
  assert r.returncode!=0 and ('selection' in r.stderr),r.stderr
 scope_negatives=[]
 for name in ('exp-halfcache','hc-weightcache'):
  sel=json.loads((P/'selection.json').read_text());sel['choices']=choices(name);path=S/(name+'.json');save(path,sel)
  for kind in ('serial','gemv','streaming','draft-rank','split','context','legacy'):
   dest=S/(name+'-'+kind);dest.mkdir(exist_ok=True)
   r=subprocess.run([str(S/'fixture'),str(path),sha(path),'1',str(dest),kind,'1','0'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
   assert r.returncode!=0 and 'p90 cached layout requires sealed' in r.stderr,(name,kind,r.stderr)
   scope_negatives.append(dict(view=name,mode=kind,passed=True))
 sel=json.loads((P/'selection.json').read_text());sel['choices']=choices('exp-halfcache');sel['choices']['hc_gate']='hc-weightcache';path=S/'combined.json';save(path,sel);dest=S/'combined';dest.mkdir(exist_ok=True)
 r=subprocess.run([str(S/'fixture'),str(path),sha(path),'1',str(dest),'positive','1','0'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
 assert r.returncode!=0 and 'p90 combined caches are not admitted' in r.stderr,r.stderr
 report['scope_negatives']=scope_negatives;report['combined_refused']=True
 report['negative_allocations']=negatives
 report.update(passed=True,negative_extent_rejected=True,selection_negatives_rejected=5,binary_sha256=sha(S/'fixture'))
 save(P/'evidence/full-shape.json',report)
if __name__=='__main__':main()
