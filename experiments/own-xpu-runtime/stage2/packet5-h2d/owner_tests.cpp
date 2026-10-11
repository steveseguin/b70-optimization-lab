#include "mock_device.hpp"
#include <iostream>
using namespace ownrt;
struct ComputeMock:MockDevice {
 Event compute(const Operation&,std::span<void* const>,std::span<const Event> deps) override {
   bool prior=auto_marker;auto_marker=false;auto e=marker(deps);auto_marker=prior;return e;
 }
};
void require(bool b){if(!b)throw std::runtime_error("test failure");}
int main(){
 for(bool independent:{false,true}){
  auto mock=std::make_unique<ComputeMock>();auto m=mock.get();Device d(std::move(mock),independent);CopyEngine copy(d);
  auto a=d.arena.allocate("a",16,Memory::device,Category::scratch,Lifetime::transaction);
  auto b=d.arena.allocate("b",16,Memory::device,Category::scratch,Lifetime::transaction);
  auto h=d.arena.allocate("h",16,Memory::shadow,Category::loader_staging,Lifetime::transfer);
  Operation op;auto e=d.compute(op,std::span(&b,1),{});auto c=copy.copy(a,0,h,0,16,{});
  bool blocked=false;try{m->finish(c);}catch(const std::logic_error&){blocked=true;}
  require(blocked!=independent);require(!d.shutdown(std::chrono::milliseconds(1)).safe_to_exit);
  m->finish(e);m->finish(c);require(d.shutdown(std::chrono::milliseconds(1)).safe_to_exit);
 }
 // Explicit cross-queue dependency still prevents early completion.
 auto mock=std::make_unique<ComputeMock>();auto m=mock.get();Device d(std::move(mock),true);CopyEngine copy(d);
 auto a=d.arena.allocate("a",16,Memory::device,Category::scratch,Lifetime::transaction);
 auto h=d.arena.allocate("h",16,Memory::pinned,Category::pinned_slab,Lifetime::transfer);
 auto e=copy.copy(a,0,h,0,16,{});Operation op;auto c=d.compute(op,std::span(&a,1),std::span(&e,1));
 bool blocked=false;try{m->finish(c);}catch(const std::logic_error&){blocked=true;}require(blocked);
 blocked=false;try{d.arena.release(a);}catch(const std::logic_error&){blocked=true;}require(blocked);
 m->finish(e);m->finish(c);require(d.shutdown(std::chrono::milliseconds(1)).safe_to_exit);
 std::cout<<"default serialization, opt-in independence, explicit dependencies, pending-release refusal, full drain: PASS\n";
}
