// CPU-only independent prepared-binding invalidation tests. No device headers.
#include "owner.hpp"
#include <algorithm>
#include <array>
#include <cstring>
#include <iostream>
#include <memory>
#include <new>
#include <stdexcept>
#include <vector>
namespace {
using namespace ownrt;
struct Store final : Operation { int value=17; };
struct Mock final : Backend {
  std::vector<Event> events;
  bool pending=false;
  size_t submissions=0;
  Mock(){events.reserve(16384);}
  std::string identity() const override{return "packet35 CPU prepared invalidation mock";}
  void* allocate(size_t n,Memory) override{return ::operator new(n);}
  void release(void* p,Memory) override{::operator delete(p);}
  Event marker(std::span<const Event>) override{auto e=next_handle();events.push_back(e);return e;}
  Event compute(const Operation& base,std::span<void*const> p,std::span<const Event>) override{
    ++submissions;*static_cast<int*>(p[0])=dynamic_cast<const Store&>(base).value;return marker({});
  }
  std::function<Event()> prepare_owned(std::shared_ptr<const Operation> op,std::span<void*const> p) override{
    std::vector<void*> pointers(p.begin(),p.end());
    return [this,op=std::move(op),pointers=std::move(pointers)]{return compute(*op,pointers,{});};
  }
  Event copy(void* d,const void* s,size_t n,std::span<const Event>) override{
    ++submissions;std::memcpy(d,s,n);return marker({});
  }
  bool complete(Event e) override{return !pending&&std::binary_search(events.begin(),events.end(),e);}
  bool wait(Event e,Deadline) override{return complete(e);}
  void synchronize() override{}
  void clear_events() override{events.clear();}
  void close_queue() override{}
  void close_context() override{}
};
void check(bool condition,const char* reason){if(!condition)throw std::runtime_error(reason);}
template<class F> void rejected(F f,const char* reason){bool caught=false;try{f();}catch(const std::logic_error&){caught=true;}check(caught,reason);}
Allocation alloc(Device& d,const std::string& name="card0:test"){
  return d.arena.allocate(name,32,Memory::device,Category::scratch,Lifetime::transaction);
}
PreparedCompute prepare(Device& d,Allocation id,int value=17){
  std::vector<PreparedCompute> commands;d.begin_capture(commands);
  try{Store op;op.value=value;std::array<Allocation,1> ids{id};d.compute(op,ids,{});d.end_capture();}
  catch(...){d.end_capture();throw;}
  check(commands.size()==1,"capture count");return std::move(commands[0]);
}
void close(Device& d){check(d.shutdown(std::chrono::seconds(1)).safe_to_exit,"mock teardown");}
}
int main(){
 size_t tests=0;
 try{
  {Device d(std::make_unique<Mock>());auto id=alloc(d);auto p=prepare(d,id);d.arena.release(id);
   auto replacement=alloc(d);check(id!=replacement,"allocation IDs reused");rejected([&]{d.issue(p);},"release/reallocate accepted stale binding");close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto id=alloc(d);auto p=prepare(d,id);d.invalidate_prepared();
   rejected([&]{d.issue(p);},"explicit invalidate ignored");auto fresh=prepare(d,id,29);d.issue(fresh);check(*static_cast<int*>(d.arena.row(id).pointer)==29,"fresh reprepare failed");close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto p=prepare(d,alloc(d));close(d);
   rejected([&]{d.issue(p);},"closed owner accepted binding");++tests;}
  {alignas(Device) std::byte storage[sizeof(Device)];auto* first=std::construct_at(reinterpret_cast<Device*>(storage),std::make_unique<Mock>());
   auto p=prepare(*first,alloc(*first));auto old_generation=first->generation();close(*first);std::destroy_at(first);
   auto* second=std::construct_at(reinterpret_cast<Device*>(storage),std::make_unique<Mock>());
   check(second->generation()!=old_generation,"owner incarnation generation reused");
   rejected([&]{second->issue(p);},"same-address new owner accepted stale binding");close(*second);std::destroy_at(second);++tests;}
  {Device d(std::make_unique<Mock>());auto p0=prepare(d,alloc(d,"card0:left"));auto p1=prepare(d,alloc(d,"card1:right"));
   d.issue(p0);rejected([&]{d.issue(p1);},"cross-card issue without drain accepted");d.retire_completed_events();d.issue(p1);close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto id=alloc(d);std::vector<PreparedCompute> commands;d.begin_capture(commands);
   Store op;std::array<Allocation,1> ids{id};std::array<Event,1> foreign{99999999};
   rejected([&]{d.compute(op,ids,foreign);},"foreign capture dependency accepted");check(commands.empty(),"foreign capture mutated command list");
   auto prior=d.compute(op,ids,{});std::array<Event,1> deps{prior};d.compute(op,ids,deps);d.end_capture();
   check(commands.size()==2,"valid capture dependency rejected");d.issue(commands[0]);d.issue(commands[1]);close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto src=alloc(d,"card0:src"),dst=alloc(d,"card0:dst");
   auto* input=static_cast<unsigned char*>(d.arena.row(src).pointer);auto* output=static_cast<unsigned char*>(d.arena.row(dst).pointer);
   for(unsigned i=0;i<32;++i)input[i]=i;std::memset(output,0,32);
   std::vector<PreparedCompute> commands;d.begin_capture(commands);CopyEngine copy(d);copy.copy(dst,4,src,8,12,{});d.end_capture();
   check(commands.size()==1,"copy capture count");d.issue(commands[0]);check(std::memcmp(output+4,input+8,12)==0&&output[3]==0&&output[16]==0,"copy offsets/extents changed");
   d.retire_completed_events();d.arena.release(src);rejected([&]{d.issue(commands[0]);},"copy source release accepted stale pointer");close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto id=alloc(d);auto p=prepare(d,id);alloc(d,"card0:unrelated");d.issue(p);
   check(*static_cast<int*>(d.arena.row(id).pointer)==17,"unrelated allocation invalidated binding");close(d);++tests;}
  {auto backend=std::make_unique<Mock>();auto* mock=backend.get();Device d(std::move(backend));auto id=alloc(d);auto p=prepare(d,id);
   d.issue(p);mock->pending=true;rejected([&]{d.invalidate_prepared();},"invalidate while pending accepted");
   rejected([&]{d.arena.release(id);},"release while pending accepted");mock->pending=false;d.retire_completed_events();d.issue(p);close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto src=alloc(d,"card0:src"),dst=alloc(d,"card0:dst");
   std::vector<PreparedCompute> commands;d.begin_capture(commands);CopyEngine copy(d);copy.copy(dst,0,src,0,4,{});d.end_capture();
   *static_cast<int*>(d.arena.row(src).pointer)=31;d.issue(commands[0]);d.retire_completed_events();
   *static_cast<int*>(d.arena.row(src).pointer)=47;d.issue(commands[0]);check(*static_cast<int*>(d.arena.row(dst).pointer)==47,"in-place content update not read");close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto src=alloc(d,"card0:src"),dst=alloc(d,"card0:dst");
   std::vector<PreparedCompute> commands;d.begin_capture(commands);CopyEngine copy(d);
   rejected([&]{copy.copy(dst,24,src,0,16,{});},"oversize captured copy accepted");
   rejected([&]{copy.copy(dst,0,dst,0,4,{});},"alias captured copy accepted");d.end_capture();check(commands.empty(),"invalid copy captured");close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto id=alloc(d);auto p=prepare(d,id,81);
   // Source operation and temporary binding array have already been destroyed.
   d.issue(p);check(*static_cast<int*>(d.arena.row(id).pointer)==81,"operation capture dangled");close(d);++tests;}
  {auto backend=std::make_unique<Mock>();auto* mock=backend.get();Device d(std::move(backend));auto id=alloc(d);
   std::vector<PreparedCompute> commands;d.begin_capture(commands);Store op;const Operation& erased=op;std::array<Allocation,1> ids{id};
   rejected([&]{d.compute(erased,ids,{});},"type-erased capture executed immediately");d.end_capture();
   check(mock->submissions==0&&commands.empty(),"preparation submitted device work");close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto target=alloc(d,"card0:target");auto capture=prepare(d,target,93);
   auto draft_scratch=alloc(d,"card0:draft:scratch");auto generation=d.generation();
   d.arena.release(draft_scratch);check(d.generation()!=generation,"draft release did not invalidate shared owner");
   check(d.arena.row(target).live,"target unexpectedly released");
   rejected([&]{d.issue(capture);},"draft scratch release accepted stale target capture");close(d);++tests;}
  {Device d(std::make_unique<Mock>());auto target=alloc(d,"card0:target");auto capture=prepare(d,target,97);
   // Model provider owns bookkeeping only; its allocations remain Engine-owned.
   struct ProviderView {Allocation scratch;};
   auto provider=std::make_unique<ProviderView>(ProviderView{alloc(d,"card0:draft:scratch")});auto scratch=provider->scratch;auto generation=d.generation();
   for(int request=0;request<4;++request){std::memset(d.arena.row(scratch).pointer,request+1,32);std::memset(d.arena.row(scratch).pointer,0,32);
    check(d.generation()==generation,"in-place draft reset invalidated target capture");d.issue(capture);d.retire_completed_events();check(*static_cast<int*>(d.arena.row(target).pointer)==97,"target changed after draft reset");}
   provider.reset();check(d.arena.row(scratch).live&&d.generation()==generation,"provider view released shared scratch");d.issue(capture);close(d);++tests;}
  std::cout<<"{\"passed\":true,\"device_executed\":false,\"tests\":"<<tests<<"}\n";return 0;
 }catch(const std::exception& e){std::cerr<<"invalidation test failed after "<<tests<<": "<<e.what()<<'\n';return 1;}
}
