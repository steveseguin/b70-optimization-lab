"""Run real production initialization/capture/allocation with payload-only mocks.
The generated test source changes no production file or arithmetic kernel.
Device extents are numerical address tokens, never mappings or model payloads.
"""
import json,subprocess,os
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices,selection
from memory_plans import ledger
import memory_gate
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
 t=t[:start]+r'''static std::map<std::string,unsigned> p83_operations;
class Host final : public packet18::LifetimeMock {
 struct Item{size_t bytes;ownrt::Memory memory;};std::map<uintptr_t,Item> dry;
 uintptr_t next=0x100000000000ULL;
 void bounds(const void*p,size_t n){auto x=uintptr_t(p);auto i=dry.upper_bound(x);require(i!=dry.begin(),"mock unknown pointer");--i;require(x-i->first<=i->second.bytes&&n<=i->second.bytes-(x-i->first),"mock copy extent");}
public:
 void* allocate(size_t n,ownrt::Memory m)override{void*p;if(m==ownrt::Memory::device){p=reinterpret_cast<void*>(next);next+=((n+4095)&~size_t(4095))+4096;}else p=::operator new(n);dry.emplace(uintptr_t(p),Item{n,m});return p;}
 void release(void*p,ownrt::Memory m)override{require(dry.at(uintptr_t(p)).memory==m,"mock memory");if(m!=ownrt::Memory::device)::operator delete(p);dry.erase(uintptr_t(p));}
 ownrt::Event copy(void*a,const void*b,size_t n,std::span<const ownrt::Event>d)override{bounds(a,n);bounds(b,n);return marker(d);}
 ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event>d)override{return marker(d);}
 std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation> op,std::span<void*const>)override{std::string name=typeid(*op).name();int status=0;char*dem=abi::__cxa_demangle(name.c_str(),nullptr,nullptr,&status);if(dem){name=dem;std::free(dem);}++p83_operations[name];return [this]{return marker({});};}
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
 m=replace(m,'hw.id=alloc("q4-head",size_t(hw.rows)*er,Category::weights);mutable_ids.erase(hw.id);','hw.id=alloc("q4-head",size_t(hw.rows)*er,Category::weights);mutable_ids.erase(hw.id);if(std::getenv("P83_SHORT_Q4")){auto &r=const_cast<std::remove_const_t<std::remove_reference_t<decltype(e.dev(0).arena.row(hw.id))>>&>(e.dev(0).arena.row(hw.id));r.bytes-=1;}')
 m=body(m,'if(store){require(store->reads.size()', '')
 (S/'mtp.hpp').write_text(m)
 (S/'main.cpp').write_text(t)
 for leaf in ('rope.bf16','mtp-manifest.tsv'):
  if not (S/leaf).exists():(S/leaf).symlink_to(P/leaf)
 entry=r'''#include <cxxabi.h>
#define main packet75_unexecuted_model_entry
#include "main.cpp"
#undef main
int main(int argc,char**argv){std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;try{
 require(argc==6,"view hash rank output negative");Options a;a.context=4096;a.cards=1;a.card=0;a.rank=std::stoi(argv[3]);a.draft_rank=1;a.target_split=0;a.mtp=true;a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[4];fs::create_directories(a.output);
 a.plan=PACKET_ROOT/"../suite-inputs-20261012/code-review/plan.tsv";a.draft_manifest=PACKET_ROOT/"mtp-manifest.tsv";
 packet26::dispatch.load((PACKET_ROOT/"dispatch-speed6.json").string());Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,false,a.draft_rank,a.target_split);
 require(arithmetic::row_bytes(iq3::Type::Q6_K,2560,6)==3380,"real expanded Q6 head stride");
 e=std::make_unique<Engine>(w,a,p);e->initialize();
 if(std::string(argv[5])=="negative"&&a.rank==1){auto id=e->weights[0].at("output.weight");auto &r=const_cast<ownrt::AllocationRecord&>(e->dev(0).arena.row(id));r.bytes-=2100;}
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 {pipeline::SpeculativeImage image(*e);if(a.rank==1)draft=std::make_unique<mtp36::DraftRuntime>(*e);
 auto count=[](const std::string& key){unsigned n=0;for(const auto&[name,value]:p83_operations)if(name.find(key)!=std::string::npos)n+=value;return n;};
 if(a.rank==1){bool q4=e->sealed_selection.draft.at("head_format")=="q4-g32";require((count("p83::Head<2560u>")>0)==q4,"draft head selection consumer");}
 std::ofstream selected(a.output/"selected-operations.txt");for(const auto&[name,value]:p83_operations)selected<<name<<" "<<value<<"\n";selected.close();
 save(a.output/"census.json",e->dev(0).arena.census());save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"rank\":"+std::to_string(a.rank)+",\"postload_device_bytes\":"+std::to_string(e->owned_bytes[0])+",\"expanded_head_stride\":3380}");draft.reset();}
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
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
 with (S/'compile.log').open('w') as f:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
 link=list(next(r['command'] for r in cmds if r['name']=='gnu-host-link'))
 link=[x for x in link if not x.endswith('/entry-main.o') and not x.endswith('own-rt-iq3-entry.cpp.o')]
 link.insert(link.index('-o'),str(S/'entry.o'));link[link.index('-o')+1]=str(S/'fixture')
 with (S/'link.log').open('w') as f:subprocess.run(link,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
 report=dict(passed=False,device_executed=False,model_payload_read=False,runs=[],sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'main.cpp',P/'mtp.hpp',P/'rank.hpp',P/'full_shape.py',*generated]},commands=[command,link])
 for name,v in views().items():
  sel=selection(name);path=S/(name+'.json');save(path,sel)
  for rank in (0,1):
   dest=S/name/str(rank);dest.mkdir(parents=True,exist_ok=True)
   cmd=[str(S/'fixture'),str(path),sha(path),str(rank),str(dest),'positive']
   with (dest/'run.log').open('w') as f:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=120)
   if r.returncode:raise ValueError('full shape failed '+str(dest))
   consumers=[line for line in (dest/'selected-operations.txt').read_text().splitlines() if line.startswith(('p83::','p33::'))]
   admission=memory_gate.check(json.loads((dest/'census.json').read_text()),ledger(name),rank,True,4096,1,0)
   report['runs'].append(dict(view=name,memory_admission=admission,selection_key_consumers_verified=True,selected_operations=consumers,selected_operations_sha256=sha(dest/'selected-operations.txt'),**json.loads((dest/'result.json').read_text())))
   print(name,rank,'PASS',flush=True)
 # Prove the full head capture exercises the actual packed extent guard.
 name='negative-head-packed';path=S/(name+'.json');sel=json.loads((P/'selection.json').read_text());sel['choices']=choices('production');sel['choices']['packed_dense']='head-packed';save(path,sel);dest=S/'negative';dest.mkdir(exist_ok=True)
 r=subprocess.run([str(S/'fixture'),str(path),sha(path),'1',str(dest),'negative'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
 (dest/'run.log').write_text(r.stdout+r.stderr);assert r.returncode!=0 and 'p74 allocation extent/alignment' in r.stderr,r.stderr
 for case in ('missing-prefix','unknown-prefix','unknown-format','combined'):
  sel=selection('q4-g32')
  if case=='missing-prefix':del sel['draft']['head_prefix']
  if case=='unknown-prefix':sel['draft']['head_prefix']='bogus'
  if case=='unknown-format':sel['draft']['head_format']='bogus'
  if case=='combined':sel['draft']['head_prefix']='coverage990'
  path=S/(case+'.json');save(path,sel);out=S/case;out.mkdir(exist_ok=True)
  r=subprocess.run([str(S/'fixture'),str(path),sha(path),'1',str(out),'positive'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
  (out/'run.log').write_text(r.stdout+r.stderr)
  assert r.returncode!=0 and ('draft' in r.stderr),r.stderr
 path=S/'q4-g32.json';out=S/'negative-q4';out.mkdir(exist_ok=True)
 r=subprocess.run([str(S/'fixture'),str(path),sha(path),'1',str(out),'positive'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120,env={**os.environ,'P83_SHORT_Q4':'1'})
 (out/'run.log').write_text(r.stdout+r.stderr)
 assert r.returncode!=0 and 'extent/lifetime' in r.stderr,r.stderr
 report.update(q4_negative_extent_rejected=True)
 report.update(passed=True,negative_extent_rejected=True,selection_negatives_rejected=4,binary_sha256=sha(S/'fixture'))
 save(P/'evidence/full-shape.json',report)
if __name__=='__main__':main()
