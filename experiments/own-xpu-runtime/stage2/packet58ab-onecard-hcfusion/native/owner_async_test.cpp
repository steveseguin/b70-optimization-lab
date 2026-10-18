#include "async_backend.hpp"
#include <iostream>
#include <cstring>
#include <algorithm>
class Mock final:public ownrt::Backend,public p58v::AsyncBackend {
public:
 bool filling=false,closed=false;unsigned foreground_waits=0,full_waits=0,releases=0;ownrt::Event ticket=0;
 std::string identity()const override{return "CPU-race-injection";}
 void* allocate(size_t n,ownrt::Memory)override{return ::operator new(n);}
 void release(void*p,ownrt::Memory)override{if(filling)throw std::logic_error("release while DMA pending");++releases;::operator delete(p);}
 ownrt::Event copy(void*a,const void*b,size_t n,std::span<const ownrt::Event>)override{std::memcpy(a,b,n);return ownrt::next_handle();}
 ownrt::Event marker(std::span<const ownrt::Event>)override{return ownrt::next_handle();}
 bool complete(ownrt::Event)override{return true;}
 bool wait(ownrt::Event,ownrt::Deadline)override{return true;}
 void synchronize()override{++full_waits;finish_fills();}
 void clear_events()override{}
 void close_queue()override{if(filling)throw std::logic_error("queue close during DMA");}
 void close_context()override{closed=true;}
 ownrt::Event fill(void*,const void*,size_t)override{filling=true;return ticket=ownrt::next_handle();}
 bool fill_complete(ownrt::Event e)override{if(e!=ticket)throw std::logic_error("foreign async event");return !filling;}
 size_t fills_pending()override{return filling;}
 void finish_fills()override{filling=false;}
 void foreground_sync()override{++foreground_waits;}
};
int main(){
 auto backend=std::make_unique<Mock>();auto* b=backend.get();ownrt::Device owner(std::move(backend));
 auto device=owner.arena.allocate("card0:cache",512,ownrt::Memory::device,ownrt::Category::weights,ownrt::Lifetime::process);
 auto host=owner.arena.allocate("host",512,ownrt::Memory::pinned,ownrt::Category::weights,ownrt::Lifetime::process);
 auto ticket=p58v::copy(owner,device,0,host,0,512);
 if(owner.in_flight()!=1||b->fill_complete(ticket))throw std::runtime_error("missing async ownership");
 owner.retire_completed_events();
 if(!b->filling||b->foreground_waits!=1||b->full_waits)throw std::runtime_error("foreground waited for maintenance");
 unsigned refused=0;
 try{owner.arena.release(device);}catch(const std::logic_error&){++refused;}
 try{p58v::copy(owner,device,1,host,0,512);}catch(const std::logic_error&){++refused;}
 try{b->fill_complete(ticket+1);}catch(const std::logic_error&){++refused;}
 auto receipt=owner.shutdown(std::chrono::seconds(1));
 if(refused!=3||!receipt.safe_to_exit||receipt.in_flight||receipt.live_bytes||!b->closed||b->releases!=2)throw std::runtime_error("unsafe final drain");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"foreground_ignores_pending_fill\":true,\"shutdown_drains_fill\":true,\"release_pending_refused\":true,\"stale_event_refused\":true,\"bounds_refused\":true}\n";
}
