#include "owner.hpp"
#include "mock_device.hpp"
#include <algorithm>
#include <iostream>
#include <stdexcept>
using namespace ownrt;
using namespace std::chrono_literals;
#define CHECK(x) do {if(!(x)) throw std::runtime_error(#x);} while(false)
template<class F> void refuses(F f) {bool caught=false; try {f();} catch(const std::exception&) {caught=true;} CHECK(caught);}
struct Fixture {
  MockDevice* mock;
  Device d;
  Fixture():Fixture(std::make_unique<MockDevice>()) {}
  explicit Fixture(std::unique_ptr<MockDevice> m):mock(m.get()),d(std::move(m)) {}
  ~Fixture() {mock->auto_marker=true; mock->finish_all();}
  Allocation alloc(std::string label,Category c=Category::weights,Lifetime l=Lifetime::process,
                   Memory m=Memory::device,std::size_t n=16) {return d.arena.allocate(label,n,m,c,l);}
};
static std::size_t index(const Receipt& r,const std::string& s) {
  auto i=std::find(r.sequence.begin(),r.sequence.end(),s); CHECK(i!=r.sequence.end()); return i-r.sequence.begin();
}
int main(int argc,char** argv) {
  try {
    CHECK(argc==2); std::string test=argv[1]; Fixture f;
    if(test=="census") {
      f.alloc("weights"); f.alloc("pin",Category::pinned_slab,Lifetime::transfer,Memory::pinned,7);
      f.alloc("shadow",Category::host_shadow,Lifetime::process,Memory::shadow,11);
      CHECK(f.d.arena.total(Memory::device)==16); CHECK(f.d.arena.total(Memory::pinned)==7);
      CHECK(f.d.arena.total(Memory::shadow)==11);
      auto census=f.d.arena.census(); CHECK(census.find("\"category\":\"weights\"")!=std::string::npos);
      CHECK(census.find("\"lifetime\":\"transfer\"")!=std::string::npos);
      CHECK(census.find("\"unmeasured_driver_shadow_bytes\":null")!=std::string::npos);
      CHECK(f.d.shutdown(0ms).live_bytes==0);
    } else if(test=="lifetime") {
      refuses([&]{f.alloc("bad",Category::weights,Lifetime::transfer);});
      refuses([&]{f.alloc("bad",Category::pinned_slab,Lifetime::transfer);});
      refuses([&]{f.alloc("empty",Category::weights,Lifetime::process,Memory::device,0);});
      auto a=f.alloc("a"); refuses([&]{f.alloc("a");}); f.d.arena.release(a);
      refuses([&]{f.d.arena.release(a);}); refuses([&]{f.d.arena.row(0);});
    } else if(test=="closed") {
      CHECK(f.d.shutdown(0ms).safe_to_exit);
      refuses([&]{f.alloc("late");}); CopyEngine copy(f.d);
      refuses([&]{copy.copy(1,0,2,0,1,{});});
      refuses([&]{f.d.graph("late",{},[]{});}); CHECK(f.d.shutdown(0ms).exit_code==0);
    } else if(test=="inflight") {
      auto a=f.alloc("a"), b=f.alloc("b"); CopyEngine copy(f.d);
      auto event=copy.copy(a,0,b,0,8,{});
      refuses([&]{f.d.arena.release(a);});
      auto r=f.d.shutdown(0ms); CHECK(!r.safe_to_exit && r.exit_code==75 && r.in_flight==1 && r.live_bytes==32);
      CHECK(!f.mock->queue_closed && !f.mock->context_closed);
      refuses([&]{f.alloc("late");});
      f.mock->finish(event); CHECK(f.d.shutdown(0ms).safe_to_exit);
    } else if(test=="order") {
      auto w=f.alloc("w"); f.alloc("kv",Category::kv,Lifetime::request);
      f.alloc("state",Category::recurrent,Lifetime::request);
      f.alloc("scratch",Category::scratch,Lifetime::transaction);
      auto g=f.alloc("static",Category::graph_static,Lifetime::graph);
      f.alloc("slab",Category::pinned_slab,Lifetime::transfer,Memory::pinned);
      bool destroyed=false;
      f.d.graph("g",{w,g},[&]{CHECK(f.d.arena.row(w).live && f.d.arena.row(g).live); destroyed=true;});
      auto r=f.d.shutdown(0ms); CHECK(destroyed && r.safe_to_exit);
      CHECK(index(r,"graph:g")<index(r,"free:workspace:scratch"));
      CHECK(index(r,"free:workspace:scratch")<index(r,"free:KV:kv"));
      CHECK(index(r,"free:KV:kv")<index(r,"free:weights:w"));
      CHECK(index(r,"free:weights:w")<index(r,"free:pinned-copy-slab:slab"));
      CHECK(index(r,"free:pinned-copy-slab:slab")<index(r,"idle-marker-complete"));
      CHECK(index(r,"idle-marker-complete")<index(r,"events-released"));
      CHECK(index(r,"events-released")<index(r,"queue-released"));
      CHECK(index(r,"queue-released")<index(r,"context-released"));
    } else if(test=="copy_bounds") {
      auto a=f.alloc("a"), b=f.alloc("b"); CopyEngine copy(f.d,8,1);
      refuses([&]{CopyEngine bad(f.d,129ull*1024*1024);});
      refuses([&]{copy.copy(a,0,b,0,9,{});}); refuses([&]{copy.copy(a,15,b,0,2,{});});
      refuses([&]{copy.copy(a,0,b,17,1,{});}); refuses([&]{copy.copy(a,0,a,0,1,{});});
      copy.copy(a,0,b,0,8,{}); refuses([&]{copy.copy(a,0,b,0,8,{});}); f.mock->finish_all();
      f.d.arena.release(a); refuses([&]{copy.copy(a,0,b,0,8,{});});
    } else if(test=="dependencies") {
      auto a=f.alloc("a"), b=f.alloc("b"), c=f.alloc("c"); CopyEngine copy(f.d);
      Fixture other; auto foreign_allocation=other.alloc("other");
      refuses([&]{copy.copy(b,0,foreign_allocation,0,1,{});});
      auto other_b=other.alloc("other-b"); CopyEngine other_copy(other.d);
      Event other_event=other_copy.copy(other_b,0,foreign_allocation,0,1,{});
      refuses([&]{copy.copy(b,0,a,0,1,std::span(&other_event,1));});
      auto* bytes=static_cast<unsigned char*>(f.d.arena.row(a).pointer); bytes[0]=93;
      Event foreign=900; refuses([&]{copy.copy(b,0,a,0,1,std::span(&foreign,1));});
      auto e=copy.copy(b,0,a,0,1,{}); auto e2=copy.copy(c,0,b,0,1,std::span(&e,1));
      refuses([&]{f.mock->finish(e2);}); f.mock->finish(e); f.mock->finish(e2);
      CHECK(*static_cast<unsigned char*>(f.d.arena.row(c).pointer)==93);
    } else if(test=="graph_lifetime") {
      auto a=f.alloc("short",Category::scratch,Lifetime::transaction);
      refuses([&]{f.d.graph("invalid",{a},[]{});});
      auto stable=f.alloc("stable",Category::graph_static,Lifetime::graph);
      f.d.graph("valid",{stable},[]{}); refuses([&]{f.d.arena.release(stable);});
    } else if(test=="marker") {
      f.alloc("a"); f.mock->auto_marker=false;
      auto r=f.d.shutdown(0ms); CHECK(!r.safe_to_exit && !r.idle_marker_complete);
      CHECK(r.live_bytes==0 && r.in_flight==1 && !f.mock->queue_closed);
      f.mock->finish_all(); CHECK(f.d.shutdown(0ms).safe_to_exit);
    } else if(test=="receipt") {
      auto a=f.alloc("a\"\n"), b=f.alloc("b"); CopyEngine copy(f.d); copy.copy(a,0,b,0,1,{});
      std::cout << f.d.shutdown(0ms).json() << '\n'; f.mock->finish_all();
      auto r=f.d.shutdown(0ms); CHECK(r.exit_code==0 && r.safe_to_exit && r.idle_marker_complete);
      std::cout << r.json() << '\n';
    } else throw std::runtime_error("unknown test");
    if(test!="receipt") std::cout << "PASS " << test << '\n'; return 0;
  } catch(const std::exception& e) {std::cerr << e.what() << '\n'; return 1;}
}
