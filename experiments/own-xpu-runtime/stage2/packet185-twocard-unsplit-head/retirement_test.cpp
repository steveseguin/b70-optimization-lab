// Tiny CPU mock operations only. Never reads model weights or loads a device.
#include "ordered_queue.hpp"
#include <array>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
using namespace ownrt;
struct Write : Operation { uint32_t value; explicit Write(uint32_t x):value(x){} };
struct Mock : Backend {
 std::vector<Event> events;size_t queries=0,syncs=0,clears=0;bool pending=false,throw_sync=false;
 std::string identity()const override{return "p76-cpu-only";}
 void* allocate(size_t n,Memory)override{return ::operator new(n);}
 void release(void*p,Memory)override{::operator delete(p);}
 Event marker(std::span<const Event>)override{auto e=next_handle();events.push_back(e);return e;}
 Event compute(const Operation&o,std::span<void*const>p,std::span<const Event>d)override{
  auto v=dynamic_cast<const Write&>(o).value;std::memcpy(p[0],&v,4);return marker(d);
 }
 std::function<Event()> prepare_owned(std::shared_ptr<const Operation>op,std::span<void*const>p)override{
  auto ptr=std::vector<void*>(p.begin(),p.end());return [this,op,ptr]{return compute(*op,ptr,{});};
 }
 Event copy(void*d,const void*s,size_t n,std::span<const Event>deps)override{std::memcpy(d,s,n);return marker(deps);}
 bool complete(Event e)override{++queries;return !pending&&std::find(events.begin(),events.end(),e)!=events.end();}
 bool wait(Event e,Deadline)override{return complete(e);}
 void synchronize()override{++syncs;if(throw_sync)throw std::runtime_error("mock asynchronous failure");if(pending)throw std::runtime_error("pending");}
 void clear_events()override{++clears;events.clear();}
 void close_queue()override{}
 void close_context()override{}
};
struct OrderedMock : Mock,OrderedQueue {
 bool ordered_prefix_complete(Event e)override{
  if(events.empty()||events.back()!=e)throw std::logic_error("terminal event differs");
  return complete(e);
 }
};
static void check(bool ok,const char*s){if(!ok)throw std::runtime_error(s);}
template<class F>void rejects(F f){bool caught=false;try{f();}catch(const std::exception&){caught=true;}check(caught,"expected refusal");}
static void close(Device&d){check(d.shutdown(std::chrono::seconds(1)).safe_to_exit,"teardown");}
static std::vector<uint32_t> trial(bool ordered,size_t&queries){
 auto b=std::make_unique<OrderedMock>();auto*m=b.get();Device d(std::move(b));
 auto a=d.arena.allocate("card0:payload",4,Memory::device,Category::scratch,Lifetime::transaction);
 std::array<Allocation,1> ids{a};std::vector<uint32_t> output;
 for(int token=0;token<4;++token){
  std::vector<PreparedCompute> commands;d.begin_capture(commands);
  for(unsigned i=0;i<768;++i)d.compute(Write(0x9e3779b9u*i+token),ids,{});
  d.end_capture();
  // Post-load allocation must not invalidate already prepared target pointers.
  auto extra=d.arena.allocate("card0:draft:"+std::to_string(token),8,Memory::pinned,Category::output_ring,Lifetime::request);
  (void)extra;
  Event tail=0;for(const auto&cmd:commands){tail=d.issue(cmd);uint32_t value;std::memcpy(&value,d.arena.row(a).pointer,4);output.push_back(value);}
  check(d.wait(tail,std::chrono::seconds(1)),"tail wait");
  const auto before=m->queries;
  if(ordered)d.retire_ordered_events();else d.retire_completed_events();
  queries+=m->queries-before;
  check(m->syncs==size_t(token+1)&&m->clears==size_t(token+1),"sync or clear elided");
  rejects([&]{d.complete(tail);}); // retired handles are invalid in both modes
 }
 close(d);return output;
}
int main(int argc,char**argv){try{
 check(argc==2,"output directory required");size_t q0=0,q1=0;auto expected=trial(false,q0),actual=trial(true,q1);
 check(expected==actual&&q0==3072&&q1==4,"byte/query identity");
 for(auto pair:{std::pair{"expected.bin",&expected},std::pair{"candidate.bin",&actual}}){std::ofstream f(std::string(argv[1])+"/"+pair.first,std::ios::binary);f.write(reinterpret_cast<const char*>(pair.second->data()),pair.second->size()*4);}
 int negative=0;
 {Device d(std::make_unique<Mock>());rejects([&]{d.retire_ordered_events();});++negative;close(d);}
 {auto b=std::make_unique<OrderedMock>();auto*m=b.get();Device d(std::move(b));auto a=d.arena.allocate("card0:x",4,Memory::device,Category::scratch,Lifetime::transaction);d.compute(Write(1),std::array<Allocation,1>{a},{});m->pending=true;rejects([&]{d.retire_ordered_events();});check(m->clears==0,"released pending");m->pending=false;++negative;close(d);}
 {Device d(std::make_unique<OrderedMock>());auto a=d.arena.allocate("card0:graph",4,Memory::device,Category::graph_static,Lifetime::graph);d.graph("test",{a},[]{});rejects([&]{d.retire_ordered_events();});++negative;close(d);}
 {Device d(std::make_unique<OrderedMock>());std::vector<PreparedCompute> commands;d.begin_capture(commands);rejects([&]{d.retire_ordered_events();});d.end_capture();++negative;close(d);}
 {auto b=std::make_unique<OrderedMock>();auto*m=b.get();Device d(std::move(b));m->throw_sync=true;rejects([&]{d.retire_ordered_events();});check(m->clears==0,"released after error");m->throw_sync=false;++negative;close(d);}
 {Device d(std::make_unique<OrderedMock>());d.retire_ordered_events();close(d);rejects([&]{d.retire_ordered_events();});++negative;}
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"cpu_model_executed\":false,\"byte_values\":3072,\"production_queries\":"<<q0<<",\"ordered_queries\":"<<q1<<",\"negative_cases\":"<<negative<<"}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
