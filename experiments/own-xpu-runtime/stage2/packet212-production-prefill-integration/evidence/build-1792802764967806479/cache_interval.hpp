#pragma once
#include "production_schedule.hpp"
// Included before Engine, after the pinned owner/cache/kernel types. No backend
// construction or device queries occur in this declaration.
namespace p212 {
class CacheInterval {
 ownrt::Device& device;p58::Cache& cache;ownrt::Allocation log;
 std::vector<ownrt::Allocation> retained;std::vector<ownrt::Event> copies;
 std::vector<p58::Entry> frozen;std::array<std::array<bool,48>,2> seen{};
 uint64_t generation=0,epoch=0;unsigned selected_row=0;bool active=false,updating=false,poisoned=false,closed=false;
public:
 CacheInterval(ownrt::Device& d,p58::Cache& c,ownrt::Allocation routes,std::vector<ownrt::Allocation> ids):device(d),cache(c),log(routes),retained(std::move(ids)){
  const auto&r=device.arena.row(log);need(r.live&&r.memory==ownrt::Memory::pinned&&r.bytes==960*sizeof(iq3::Route),"p212 retained route slab");retained.push_back(log);generation=device.generation();verify();
 }
 bool running()const{return active;}
 bool in_update()const{return updating;}
 bool protects(ownrt::Allocation id)const{return std::find(retained.begin(),retained.end(),id)!=retained.end();}
 void poison()noexcept{poisoned=true;}
 void admit()const{
  need(!poisoned&&!closed&&!updating&&device.generation()==generation,"p212 live interval owner/generation");
 }
 void verify()const{admit();for(auto id:retained)need(device.arena.row(id).live,"p212 indirect storage lifetime");
  if(active){const auto&table=cache.table();need(table.size()==frozen.size(),"p212 frozen table extent");for(size_t i=0;i<table.size();++i){const auto&a=table[i];const auto&b=frozen[i];need(a.gate==b.gate&&a.up==b.up&&a.down==b.down&&a.generation==b.generation,"p212 Cache metadata changed during readers");}}
 }
 void begin(){verify();need(!active&&!updating&&copies.empty()&&device.in_flight()==0,"p212 frozen interval entry");need(cache.table().size()==48*512,"p212 exact production cache");frozen=cache.table();seen={};selected_row=0;epoch=cache.begin_position();active=true;}
 void row(unsigned value){need(active&&value<2,"p212 row admission");selected_row=value;}
 ownrt::Event retain(unsigned layer,ownrt::Allocation source){admit();need(active&&layer<48&&!seen[selected_row][layer],"p212 exactly once row-layer route");const auto&r=device.arena.row(source);need(r.live&&r.memory==ownrt::Memory::device&&r.bytes>=10*sizeof(iq3::Route),"p212 actual route extent");ownrt::CopyEngine copy(device);auto event=copy.copy(log,route_offset(selected_row,layer)*sizeof(iq3::Route),source,0,10*sizeof(iq3::Route),{});copies.push_back(event);seen[selected_row][layer]=true;return event;}
 // Engine calls this after waiting its tail and before *every* event retirement.
 // Never interpret a missing/retired event as completion.
 void consume(){for(auto e:copies)need(device.wait(e,std::chrono::seconds(60))&&device.complete(e),"p212 route copy incomplete");copies.clear();}
 std::vector<uint32_t> finish(){verify();need(active&&copies.empty()&&device.in_flight()==0,"p212 interval readers not drained");for(const auto&row:seen)for(bool present:row)need(present,"p212 missing captured route");const auto*p=static_cast<const iq3::Route*>(device.arena.row(log).pointer);std::vector<uint32_t> ids;ids.reserve(960);for(unsigned i=0;i<960;++i)ids.push_back(p[i].expert_id);auto result=chronological_routes(ids);cache.finish_position(epoch,true);active=false;updating=true;return result;}
 void committed(){need(updating&&!active&&!poisoned&&device.in_flight()==0,"p212 update commit boundary");updating=false;verify();}
 void close_after_drain(){if(closed)return;need(copies.empty()&&device.in_flight()==0,"p212 close before completion");if(active){cache.finish_position(epoch,true);active=false;}if(updating)cache.close_failed(true);else cache.close();closed=true;}
};
} // namespace p212
