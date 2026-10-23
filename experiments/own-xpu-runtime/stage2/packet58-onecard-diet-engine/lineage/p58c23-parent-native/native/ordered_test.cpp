#include "ordered_retirement.hpp"
#include <cstring>
#include <iostream>
#include <map>
#include <vector>
using namespace ownrt;
static void require(bool yes,const char* text){if(!yes)throw std::runtime_error(text);}
class Mock final:public Backend,public p58v::AsyncBackend,public ForegroundPrefix {
public:
 ForegroundTails tails;std::map<Event,bool> copies;
 bool compute_ready=true,copy_ready=true,filling=false,closed=false;
 unsigned queries=0,prefix_queries=0,syncs=0,clears=0,full_waits=0;Event fill_ticket=0;
 std::string identity()const override{return "CPU-two-in-order-foreground-queues";}
 void* allocate(size_t n,Memory)override{return ::operator new(n);}
 void release(void* p,Memory)override{require(!filling,"release while maintenance pending");::operator delete(p);}
 Event record(bool copy){Event e=next_handle();copies[e]=copy;tails.record(e,copy);return e;}
 Event copy(void* d,const void* s,size_t n,std::span<const Event>)override{std::memcpy(d,s,n);return record(true);}
 Event marker(std::span<const Event>)override{return record(false);}
 Event compute(const Operation&,std::span<void*const>,std::span<const Event>)override{return record(false);}
 bool complete(Event e)override{++queries;return copies.at(e)?copy_ready:compute_ready;}
 bool foreground_prefix_complete()override{++prefix_queries;return tails.complete([this](Event e){return complete(e);});}
 bool wait(Event e,Deadline)override{return complete(e);}
 void foreground_sync()override{require(compute_ready&&copy_ready,"synchronization while pending");++syncs;}
 void clear_events()override{++clears;copies.clear();tails.clear();}
 void synchronize()override{++full_waits;finish_fills();foreground_sync();}
 void close_queue()override{require(!filling,"close during maintenance");}
 void close_context()override{closed=true;}
 Event fill(void*,const void*,size_t)override{filling=true;return fill_ticket=next_handle();}
 bool fill_complete(Event e)override{require(e==fill_ticket,"foreign maintenance event");return !filling;}
 size_t fills_pending()override{return filling;}
 void finish_fills()override{filling=false;}
};
int main(){try{
 std::vector<uint8_t> reference;
 for(bool ordered:{false,true}) {
  auto impl=std::make_unique<Mock>();auto* b=impl.get();Device d(std::move(impl));set_ordered_retirement(d,ordered);
  auto x=d.arena.allocate("card0:x",512,Memory::device,Category::weights,Lifetime::process);
  auto y=d.arena.allocate("card0:y",512,Memory::pinned,Category::weights,Lifetime::process);
  auto* src=static_cast<uint8_t*>(d.arena.row(y).pointer);for(unsigned i=0;i<512;++i)src[i]=uint8_t(i*37+11);
  CopyEngine copy(d);
  auto tick=[&]{Operation op;return d.compute(static_cast<const Operation&>(op),std::span<const Allocation>(&x,1),{});};
  Event tail=0;for(unsigned i=0;i<512;++i){tail=copy.copy(x,0,y,0,512,{});tail=tick();}
  b->queries=0;d.retire_completed_events();require(b->queries==(ordered?2u:1024u),"completion query count");
  std::vector<uint8_t> actual(512);std::memcpy(actual.data(),d.arena.row(x).pointer,512);if(!ordered)reference=actual;else require(reference==actual,"retirement changed bytes");
  require(b->tails.compute==0&&b->tails.copy==0,"cleared terminals retained");
  // Each foreground queue independently blocks retirement, including when
  // its event is not the final event in the owner's combined ledger.
  copy.copy(x,0,y,0,512,{});tick();
  unsigned refused=0;
  b->copy_ready=false;try{d.retire_completed_events();}catch(const std::logic_error&){++refused;}
  b->copy_ready=true;b->compute_ready=false;try{d.retire_completed_events();}catch(const std::logic_error&){++refused;}
  try{set_ordered_retirement(d,!ordered);}catch(const std::logic_error&){++refused;}
  require(refused==3&&b->clears==1,"pending prefix cleared or switched");b->compute_ready=true;d.retire_completed_events();
  auto ticket=p58v::copy(d,x,0,y,0,512);require(d.in_flight()==1,"maintenance ownership missing");
  auto waits=b->full_waits;d.retire_completed_events();require(b->filling&&b->full_waits==waits,"retirement waited for maintenance");
  bool blocked=false;try{set_ordered_retirement(d,!ordered);}catch(const std::logic_error&){blocked=true;}require(blocked,"switch during maintenance admitted");
  blocked=false;try{d.arena.release(x);}catch(const std::logic_error&){blocked=true;}require(blocked,"pending allocation released");
  b->finish_fills();set_ordered_retirement(d,!ordered);set_ordered_retirement(d,ordered);
  auto receipt=d.shutdown(std::chrono::seconds(1));require(receipt.safe_to_exit&&!receipt.in_flight&&!receipt.live_bytes&&b->closed,"owner did not drain");
 }
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"bytes_equal\":512,\"production_queries\":1024,\"ordered_queries\":2,\"both_pending_foreground_queues_refused\":true,\"maintenance_ownership_preserved\":true,\"quiescent_switch_refused_while_busy\":true}\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
