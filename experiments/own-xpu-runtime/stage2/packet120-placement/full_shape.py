"""Run real production initialization/capture/allocation with payload-only mocks.
The generated test source changes no production file or arithmetic kernel.
Device extents are numerical address tokens, never mappings or model payloads.
"""
import json,subprocess,gzip,shutil
from compile_turn import turn
import os,hashlib
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices,selection,placement_for,PLACEMENTS
from memory_plans import plan
from memory_gate import check,ARENA_LIMIT_BYTES
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
 t=t[:start]+r'''static std::map<std::string,unsigned> p80_operations,p93_head_operations;
static const void* p93_target_head=nullptr;
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
 std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation> op,std::span<void*const> pointers)override{std::string name=typeid(*op).name();int status=0;char*dem=abi::__cxa_demangle(name.c_str(),nullptr,nullptr,&status);if(dem){name=dem;std::free(dem);}++p80_operations[name];if(p93_target_head&&!pointers.empty()&&pointers[0]==p93_target_head)++p93_head_operations[name];return [this]{return marker({});};}
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
 std::unique_ptr<p105::Runtime> head_runtime;if(e->split_head())head_runtime=std::make_unique<p105::Runtime>(*e);
 if(a.rank==1)p93_target_head=e->dev(0).arena.row(e->weights[0].at("output.weight")).pointer;
 write_plan(a.output/"native-plan.json",p,w,a.cards,a);
 if(negative!="positive"){
  require(a.rank==1,"target-head mutation only on rank1");
  auto found=e->weights[0].find("output.weight");require(found!=e->weights[0].end(),"negative head missing");
  auto &r=const_cast<std::remove_const_t<std::remove_reference_t<decltype(e->dev(0).arena.row(found->second))>>&>(e->dev(0).arena.row(found->second));
  auto saved=r;auto id=found->second;restore=[&,id,saved]{auto &row=const_cast<std::remove_const_t<std::remove_reference_t<decltype(e->dev(0).arena.row(id))>>&>(e->dev(0).arena.row(id));row=saved;};
  if(negative=="short")--r.bytes;else if(negative=="misaligned")r.pointer=reinterpret_cast<void*>(uintptr_t(r.pointer)+1);else throw std::invalid_argument("negative mode");
 }
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 {pipeline::SpeculativeImage image(*e);const auto before_draft=p80_operations;if(a.rank==a.draft_rank)draft=std::make_unique<mtp36::DraftRuntime>(*e);
 auto draft_count=[&](const std::string& key){unsigned n=0;for(const auto&[name,value]:p80_operations)if(name.find(key)!=std::string::npos)n+=value-(before_draft.contains(name)?before_draft.at(name):0);return n;};
 if(a.rank==1){
  const bool split=e->sealed_selection.draft.at("qsa_attention")=="packet59";
  require((draft_count("p49::Attention<0>")==1)==split,"draft split32 startup dispatch");
  require((draft_count("p30integrated::Attention")>0)==!split,"draft production attention dispatch");
  require(draft_count("p59::GateMix<320u>")==3,"three inherited draft HC mixtures");
 }
 auto count=[](const std::string& key){unsigned n=0;for(const auto&[name,value]:p80_operations)if(name.find(key)!=std::string::npos)n+=value;return n;};
 const auto& choice=e->sealed_selection.choices;
 require((count("p82rec::Kernel<true>")>0)==(choice.at("recurrence")=="rec-parallel"),"rec-parallel consumer");
 require((count("p82brec::Kernel<true>")>0)==(choice.at("recurrence")=="rec-both-plus"),"rec-both-plus consumer");
 const auto& head=choice.at("head");const bool packed=head=="head-transpose";const bool split=e->split_head();
 require((count("p93::Kernel<2u>")>0)==(a.rank==1&&packed),"transposed head consumer");
 const auto expert=p100::gate_choice(choice.at("experts"));
 require((count("p95exp::Kernel")>0)==(expert=="exp-grid-prefetch"||expert=="exp-grid-prefetch+halfcache"),"prefetch consumer");
 require((count("p90exp::Kernel")>0)==(expert=="exp-halfcache"),"halfcache consumer");
 require((count("p100::Kernel<2u>")>0)==p100::tiled(choice.at("experts")),"tile16 down consumer");
 require((count("p65::Kernel<(iq3::Type)20, 640u, 64u, false, true, 0u>")>0)==!p100::tiled(choice.at("experts")),"production down consumer");
 require(count("p60::Kernel<2, true, false, false, false>")>0,"HC wide consumer");
 require((count("p60::Kernel<1, false, false, false, true>")>0)==(choice.at("hc_norm")=="consumer"),"norm fusion consumer");
 require((count("p60::Kernel<0, false, false, false, false>")>0)==(choice.at("hc_norm")!="consumer"),"norm skip consumer");
 require((count("p78route::Kernel")>0)==(choice.at("route")=="route-fast"&&choice.at("other_fusion")=="production"),"route consumer");
 require((count("p109route::Kernel")>0)==(choice.at("other_fusion")=="fused"),"fusion route consumer");
 require(e->reply_report.enabled==(a.rank==1&&choice.at("host_retire")=="reply-first"),"reply-first consumer");
 if(a.rank==1){
  auto id=e->weights[0].at("output.weight");const auto&r=e->dev(0).arena.row(id);
  require(r.bytes==size_t(split?p105::prefix:248320)*(packed?2100:3380),"real selected target-head allocation extent");
  require(count("p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>")>0,"unchanged expanded draft head consumer");
  const std::string expected=head=="head-plane"?"p93::Kernel<1u>":head=="head-transpose"?"p93::Kernel<2u>":"p33::Kernel<0u, (iq3::Type)14, 2560u, 1u>";
  require(p93_head_operations.size()==1&&p93_head_operations.contains(expected),"selected kernel bound to real target head allocation");
 }
 std::ofstream selected(a.output/"selected-operations.txt");for(const auto&[name,value]:p80_operations)selected<<name<<" "<<value<<"\n";selected.close();
 require(e->ordered_retirement==(a.rank==1&&(choice.at("host_retire")=="ordered"||choice.at("host_retire")=="reply-first")),"host retirement selection consumer");
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
 base=[x.replace(str(P.parent/'packet97-record-bundle'),str(P)) if x.startswith('-I') else x for x in base if not x.startswith('-O')]+['-O0','-I'+str(P)]
 command=[*base,'-c',str(S/'entry.cpp'),'-o',str(S/'entry.o')]
 with turn(),(S/'compile.log').open('w') as f:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
 link=list(next(r['command'] for r in cmds if r['name']=='gnu-host-link'));link=[x for x in link if not x.endswith('/entry-main.o') and not x.endswith('own-rt-iq3-entry.cpp.o')];link.insert(link.index('-o'),str(S/'entry.o'));link[link.index('-o')+1]=str(S/'fixture')
 with turn(),(S/'link.log').open('w') as f:subprocess.run(link,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
 report=dict(passed=False,device_executed=False,model_payload_read=False,runs=[],sources={},commands=[command,link])
 for label,v in views().items():
  path=S/'selection.json';save(path,selection(v));ledger=plan(v);placement=placement_for(label);split=PLACEMENTS[placement][1]
  for rank in (0,1):
   limits();dest=S/'scratch';dest.mkdir();cmd=[str(S/'fixture'),str(path),sha(path),str(rank),str(dest),'positive','1',str(split)]
   try:
    r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    if r.returncode:raise ValueError(label+' rank'+str(rank)+': '+r.stderr)
    native=json.loads((dest/'result.json').read_text());census=json.loads((dest/'census.json').read_text());reported=json.loads((dest/'native-plan.json').read_text())
    weights={r['label'].split('weight:',1)[1]:r['bytes'] for r in census['allocations'] if r['live'] and r['memory']=='device' and r['label'].startswith('card0:weight:')}
    planned={r['name']:r['stored_bytes'] for r in reported['tensor_owners']}
    assert all(planned[k]==n for k,n in weights.items() if k in planned)
    packed=False;split_head=v[13]=='split';expected_head=(202240*3380 if rank==1 else 46080*3380) if split_head else (248320*3380 if rank==1 else 0);expected_prefix=0
    assert weights.get('output.weight',0)==expected_head
    prefix=[r for r in census['allocations'] if r['live'] and r['memory']=='device' and r['label']=='card0:draft:shared-head-host']
    assert sum(r['bytes'] for r in prefix)==expected_prefix
    if rank==1:
     assert json.loads((dest/'draft-memory.json').read_text())['head_weight_shared']==(not packed)
     d=json.loads((dest/'draft-prefix.json').read_text());assert d['rows']==int(v[14]) and d['extra_weight_bytes']==expected_prefix
    gate=check(census,ledger,rank,mtp=True,context=4096,draft_rank=1,target_split=split)
    assert census['totals']['device']==ledger['placements'][placement]['capacities']['4096']['ranks'][rank]['arena_device_bytes'],'post-build census differs from census-first'
    artifacts={}
    for leaf in ('census.json','selected-operations.txt','draft-prefix.json','draft-memory.json','native-plan.json','result.json'):
     if (dest/leaf).exists():
      f=P/'evidence'/('shape-'+hashlib.sha256((dest/leaf).read_bytes()).hexdigest()+'-'+leaf+'.gz');f.write_bytes(gzip.compress((dest/leaf).read_bytes(),mtime=0));artifacts[leaf]=dict(path=str(f.relative_to(ROOT)),sha256=sha(f))
    report['runs'].append(dict(view=label,placement=placement,command=cmd,selection_key_consumers_verified=True,memory=gate,artifacts=artifacts,target_head_bytes=expected_head,draft_prefix_bytes=expected_prefix,arena_headroom_bytes=ARENA_LIMIT_BYTES-census['totals']['device'],**native))
   finally:shutil.rmtree(dest)
  print(label,'both ranks startup/admission PASS',flush=True)
 from math_gate import closure
 for f in [*closure(),P/'full_shape.py',P/'memory_plans.py',P/'memory_gate.py',P/'bundle_selection.py',P/'selection-template.json',P/'dispatch-speed6.json',*generated]:report['sources'][str(f.relative_to(ROOT))]=sha(f)
 report.update(passed=True,binary_sha256=sha(S/'fixture'));save(P/'evidence/full-shape.json',report)
if __name__=='__main__':main()
