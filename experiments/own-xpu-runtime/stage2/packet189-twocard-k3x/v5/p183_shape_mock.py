"""Payload-only full-shape mocks, ported byte-for-byte in logic from the packet root's
full_shape.py generate() (packet136/142 lineage), parameterized by the source mirror,
output folder and packet root. The parent module cannot be imported here: its
build_engine import targets a different packet layout. No production file changes.
"""
import json
from pathlib import Path
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
def generate(mirror,S,P):
 S.mkdir(exist_ok=True)
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
 return S
