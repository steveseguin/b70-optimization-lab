// Host-only actual-family front ends -> mock queue. Never includes SYCL.
#include "owner.hpp"
#include "performance.hpp"
#include "p25_bridge.hpp"
#include "p28/submit.hpp"
#include "expert_down.hpp"
#include "small_gemv.hpp"
#include "specialised_submit.hpp"
#include "round2_submit.hpp"
#include "adapter.hpp"
#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <new>
#include <typeinfo>
static thread_local bool count_allocations=false;
static thread_local size_t allocation_calls=0;
extern "C" void* __real_malloc(size_t);
extern "C" void* __real_calloc(size_t,size_t);
extern "C" void* __real_realloc(void*,size_t);
extern "C" void* __wrap_malloc(size_t n){if(count_allocations)++allocation_calls;return __real_malloc(n);}
extern "C" void* __wrap_calloc(size_t n,size_t s){if(count_allocations)++allocation_calls;return __real_calloc(n,s);}
extern "C" void* __wrap_realloc(void* p,size_t n){if(count_allocations)++allocation_calls;return __real_realloc(p,n);}
void* operator new(size_t n){if(count_allocations)++allocation_calls;void* p=__real_malloc(n?n:1);if(!p)throw std::bad_alloc();return p;}
void* operator new[](size_t n){return ::operator new(n);}
void operator delete(void* p)noexcept{std::free(p);}void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,size_t)noexcept{std::free(p);}void operator delete[](void* p,size_t)noexcept{std::free(p);}
void* operator new(size_t n,std::align_val_t a){if(count_allocations)++allocation_calls;void* p=nullptr;if(posix_memalign(&p,size_t(a),n?n:1))throw std::bad_alloc();return p;}
void* operator new[](size_t n,std::align_val_t a){return ::operator new(n,a);}
void operator delete(void* p,std::align_val_t)noexcept{std::free(p);}void operator delete[](void* p,std::align_val_t)noexcept{std::free(p);}
void operator delete(void* p,size_t,std::align_val_t)noexcept{std::free(p);}void operator delete[](void* p,size_t,std::align_val_t)noexcept{std::free(p);}
struct Mock final:ownrt::Backend {
 uint64_t digest=0,issued=0;std::vector<ownrt::Event> events;
 Mock(){events.reserve(16384);}
 std::string identity()const override{return "CPU issue-only mock; no device execution";}
 void* allocate(size_t,ownrt::Memory)override{return ::operator new(64,std::align_val_t(64));}
 void release(void* p,ownrt::Memory)override{::operator delete(p,std::align_val_t(64));}
 ownrt::Event marker(std::span<const ownrt::Event>)override{auto e=ownrt::next_handle();events.push_back(e);return e;}
 ownrt::Event call(uint64_t kind,std::span<void*const> p){digest=digest*1099511628211ull+kind;for(auto v:p)digest=digest*1099511628211ull+reinterpret_cast<uintptr_t>(v);++issued;return marker({});}
 ownrt::Event compute(const ownrt::Operation& op,std::span<void*const> p,std::span<const ownrt::Event>)override{return call(reinterpret_cast<uintptr_t>(&typeid(op)),p);}
 std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation> op,std::span<void*const> p)override{
  std::vector<void*> bound(p.begin(),p.end());auto kind=reinterpret_cast<uintptr_t>(&typeid(*op));return [this,bound=std::move(bound),kind]{return call(kind,bound);};
 }
 ownrt::Event copy(void*,const void*,size_t,std::span<const ownrt::Event>)override{throw std::logic_error("benchmark never copies data");}
 bool complete(ownrt::Event e)override{return std::binary_search(events.begin(),events.end(),e);}
 bool wait(ownrt::Event e,ownrt::Deadline)override{return complete(e);}
 void synchronize()override{}void clear_events()override{events.clear();}void close_queue()override{}void close_context()override{}
};
using integrated::Matrix;using ownrt::Allocation;
int main(){
 auto backend=std::make_unique<Mock>();Mock* mock=backend.get();ownrt::Device d(std::move(backend));
 size_t next_allocation=0;auto alloc=[&](size_t n){return d.arena.allocate("card0:mock"+std::to_string(next_allocation++),n,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction);};
 auto matrix=[&](iq3::Type t,size_t rows,size_t cols,unsigned v,bool expert=false){Matrix m{};m.type=t;m.rows=rows;m.columns=cols;m.experts=expert?10:1;m.count=expert?10:1;m.w=alloc(size_t(m.experts)*rows*integrated::arithmetic::row_bytes(t,cols,v));m.x=alloc(size_t(m.count)*cols*2);m.y=alloc(size_t(m.count)*rows*2);m.workspace=alloc(rows*m.count*8*4);if(expert){m.routes=alloc(10*sizeof(iq3::Route));m.status=alloc(40);}return m;};
 struct Case {std::string name;std::function<void()> legacy;};std::vector<Case> cases;
 auto dense=matrix(iq3::Type::Q8_0,640,2560,6),expert=matrix(iq3::Type::IQ4_NL,2560,640,2,true);
 cases.push_back({"dense_r5",[&]{integrated::dense(d,dense,6);}});
 cases.push_back({"experts_r5",[&]{integrated::experts(d,{expert},false);}});
 cases.push_back({"p25_gemv",[&]{packet26::p25bridge::submit(d,{dense},"p25.rows4",false,6);}});
 cases.push_back({"p27_gemv",[&]{packet26::p25bridge::submit(d,{dense},"p27.packed64",false,6);}});
 cases.push_back({"p28_gemv",[&]{p28::submit(d,{dense},"p28.dense.rows4",false,6);}});
 cases.push_back({"p29_gemv",[&]{p29::submit(d,{expert},"p29.down.rows4",false,2);}});
 auto xf=alloc(dense.columns*4);cases.push_back({"p27_input_prepare",[&]{packet26::p25bridge::prepare_input(d,dense.x,xf,dense.columns);}});
 std::vector<Matrix> small;std::vector<unsigned> variants;for(auto sh:packet27::small::shapes("small.hc")){small.push_back(matrix(sh.type,sh.rows,sh.columns,sh.variant));variants.push_back(sh.variant);}
 cases.push_back({"small_gemv_fusion",[&]{packet27::small::submit(d,"small.hc",small,variants);}});
 std::array<Allocation,19> ngargs;for(auto& id:ngargs)id=alloc(64*1024*1024);auto scratch=alloc(64*1024*1024);
 ng::Shape norm{};norm.op=ng::norm;norm.width=2560;norm.heads=4;
 cases.push_back({"specialised",[&]{specialised::submit(d,norm,ngargs,scratch);}});
 ng::Shape select{};select.op=ng::select;
 cases.push_back({"round2",[&]{round2::submit(d,select,ngargs,scratch);}});
 integrated::Spec spec{};spec.g.context=128;spec.g.budget=128;spec.g.h=2560;spec.op=integrated::Op::silu_div4;spec.ni=1;spec.no=1;spec.sizes[0]=spec.sizes[1]=2560;spec.types[0]=spec.types[1]=integrated::Scalar::bf16;
 std::array<Allocation,7> args;for(auto& id:args)id=alloc(64*1024*1024);auto control=alloc(64*1024*1024),score=alloc(64*1024*1024),probability=alloc(64*1024*1024);
 cases.push_back({"packet18_parallel",[&]{packet18::submit_parallel(d,spec,args,control,score,probability);}});
 auto down=alloc(2560*10*2),prob=alloc(10*4),out=alloc(2560*2);
 cases.push_back({"combine",[&]{integrated::mixture(d,down,prob,out,2560);}});
 integrated::Spec check{};check.special=integrated::Special::check_status;check.ni=1;check.sizes[0]=10;check.types[0]=integrated::Scalar::u32;
 std::array<Allocation,6> checkargs;for(auto& id:checkargs)id=alloc(64);
 cases.push_back({"check",[&]{packet18::submit_parallel(d,check,checkargs,control,score,probability);}});
 integrated::Spec commit{};commit.special=integrated::Special::commit;std::array<Allocation,5> commitargs;for(auto& id:commitargs)id=alloc(64);
 cases.push_back({"commit",[&]{packet18::submit_parallel(d,commit,commitargs,control,score,probability);}});
 constexpr unsigned repeats=11,iterations=2048;bool first=true;size_t total_new_allocations=0;
 std::cout<<"{\"schema\":\"packet35.actual-family-mock-issue.v1\",\"device_executed\":false,\"warmup_iterations\":2,\"measured_iterations\":9,\"sites_per_iteration\":"<<iterations<<",\"families\":[";
 for(auto& c:cases){
  std::vector<ownrt::PreparedCompute> prepared;d.begin_capture(prepared);c.legacy();d.end_capture();
  mock->digest=0;mock->issued=0;c.legacy();auto expected=mock->digest;auto launches=mock->issued;d.retire_completed_events();
  mock->digest=0;mock->issued=0;for(auto& p:prepared)d.issue(p);bool parity=mock->digest==expected&&mock->issued==launches;d.retire_completed_events();if(!parity||prepared.size()!=launches)throw std::logic_error("mock argument/type/order mismatch");
  std::array<double,9> before{},after{};size_t oldalloc=0,newalloc=0;
  for(unsigned repeat=0;repeat<repeats;++repeat)for(int mode=0;mode<2;++mode){
   allocation_calls=0;count_allocations=true;auto start=std::chrono::steady_clock::now();
   for(unsigned i=0;i<iterations;++i){if(mode){for(auto& p:prepared)d.issue(p);}else c.legacy();}
   auto end=std::chrono::steady_clock::now();count_allocations=false;
   auto ns=std::chrono::duration<double,std::nano>(end-start).count()/(iterations*launches);
   if(repeat>=2){(mode?after:before)[repeat-2]=ns;if(mode)newalloc+=allocation_calls;else oldalloc+=allocation_calls;}
   d.retire_completed_events();
  }
  std::sort(before.begin(),before.end());std::sort(after.begin(),after.end());total_new_allocations+=newalloc;
  std::cout<<(first?"":",")<<"{\"family\":"<<ownrt::quote(c.name)<<",\"launches_per_site\":"<<launches<<",\"before_ns\":"<<before[4]<<",\"after_ns\":"<<after[4]<<",\"before_allocations\":"<<oldalloc<<",\"after_allocations\":"<<newalloc<<",\"argument_pointer_type_order_parity\":true}";first=false;
 }
 auto closed=d.shutdown(std::chrono::seconds(10));if(!closed.safe_to_exit)throw std::logic_error("mock shutdown failed");
 std::cout<<"],\"prepared_allocation_calls\":"<<total_new_allocations<<",\"passed\":"<<(total_new_allocations==0?"true":"false")<<"}\n";return total_new_allocations?1:0;
}
