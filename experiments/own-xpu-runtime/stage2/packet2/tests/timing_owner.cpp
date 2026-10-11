// CPU mock only: profiling preserves the event ownership/completion boundary.
#include "mock_device.hpp"
#include <iostream>
using namespace ownrt;
struct ProfileMock : MockDevice {
  EventTiming timing(Event e) override {if(!complete(e))throw std::logic_error("pending");return {100,200};}
};
template<class F> void refuses(F f) {try{f();}catch(const std::exception&){return;}throw std::runtime_error("expected refusal");}
int main() {
  auto backend=std::make_unique<ProfileMock>();auto* mock=backend.get();Device d(std::move(backend));
  auto a=d.arena.allocate("a",8,Memory::device,Category::scratch,Lifetime::transaction);
  auto b=d.arena.allocate("b",8,Memory::device,Category::scratch,Lifetime::transaction);
  CopyEngine copy(d);auto event=copy.copy(a,0,b,0,8,{});
  refuses([&]{d.timing(event+1);}); // foreign event
  refuses([&]{d.timing(event);}); // owned but incomplete
  mock->finish(event);auto t=d.timing(event);
  if(t.start_ns!=100 || t.end_ns!=200)throw std::runtime_error("profiling forwarding");
  if(!d.shutdown(std::chrono::milliseconds(0)).safe_to_exit)throw std::runtime_error("teardown");
  refuses([&]{d.timing(event);}); // released event
  std::cout<<"PASS CPU profiling ownership, completion, forwarding and release\n";
}
