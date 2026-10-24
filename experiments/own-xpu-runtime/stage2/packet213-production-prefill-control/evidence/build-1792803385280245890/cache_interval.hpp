#pragma once
#include "production_control.hpp"
#include "cache_transition.hpp"
// Included before Engine, after the pinned owner/cache/kernel types. No backend
// construction or device queries occur in this declaration.
namespace p213 {
class CacheInterval {
 ownrt::Device& device;p58::Cache& cache;ownrt::Allocation log;
 std::vector<ownrt::Allocation> retained;std::vector<ownrt::Event> copies;
 std::vector<p58::Entry> frozen;std::array<std::array<bool,48>,2> seen{};
 uint64_t generation=0,epoch=0;unsigned selected_row=0;bool active=false;CacheTransition transitions;
public:
 CacheInterval(ownrt::Device& d,p58::Cache& c,ownrt::Allocation routes,std::vector<ownrt::Allocation> ids):device(d),cache(c),log(routes),retained(std::move(ids)){
  const auto&r=device.arena.row(log);need(r.live&&r.memory==ownrt::Memory::pinned&&r.bytes==960*sizeof(iq3::Route),"p213 retained route slab");retained.push_back(log);generation=device.generation();verify();
 }
 bool running()const{return active;}
 bool in_update()const{return transitions.phase()==CacheTransition::Phase::updating;}
 bool protects(ownrt::Allocation id)const{return std::find(retained.begin(),retained.end(),id)!=retained.end();}
 void poison()noexcept{transitions.poison();}
 void admit()const{
  need(!transitions.poisoned()&&transitions.phase()!=CacheTransition::Phase::closed&&!in_update()&&device.generation()==generation,"p213 live interval owner/generation");
 }
 void verify()const{admit();for(auto id:retained)need(device.arena.row(id).live,"p213 indirect storage lifetime");
  if(active){const auto&table=cache.table();need(table.size()==frozen.size(),"p213 frozen table extent");for(size_t i=0;i<table.size();++i){const auto&a=table[i];const auto&b=frozen[i];need(a.gate==b.gate&&a.up==b.up&&a.down==b.down&&a.generation==b.generation,"p213 Cache metadata changed during readers");}}
 }
 void begin(){verify();need(!active&&transitions.phase()==CacheTransition::Phase::idle&&copies.empty()&&device.in_flight()==0,"p213 frozen interval entry");need(cache.table().size()==48*512,"p213 exact production cache");frozen=cache.table();seen={};selected_row=0;epoch=transitions.begin(cache);active=true;}
 void row(unsigned value){need(active&&value<2,"p213 row admission");selected_row=value;}
 ownrt::Event retain(unsigned layer,ownrt::Allocation source){admit();need(active&&layer<48&&!seen[selected_row][layer],"p213 exactly once row-layer route");const auto&r=device.arena.row(source);need(r.live&&r.memory==ownrt::Memory::device&&r.bytes>=10*sizeof(iq3::Route),"p213 actual route extent");ownrt::CopyEngine copy(device);auto event=copy.copy(log,route_offset(selected_row,layer)*sizeof(iq3::Route),source,0,10*sizeof(iq3::Route),{});copies.push_back(event);seen[selected_row][layer]=true;return event;}
 // Engine calls this after waiting its tail and before *every* event retirement.
 // Never interpret a missing/retired event as completion.
 void consume(){for(auto e:copies)need(device.wait(e,std::chrono::seconds(60))&&device.complete(e),"p213 route copy incomplete");copies.clear();}
 std::vector<uint32_t> finish(){verify();need(active&&copies.empty()&&device.in_flight()==0,"p213 interval readers not drained");for(const auto&row:seen)for(bool present:row)need(present,"p213 missing captured route");const auto*p=static_cast<const iq3::Route*>(device.arena.row(log).pointer);std::vector<uint32_t> ids;ids.reserve(960);for(unsigned i=0;i<960;++i)ids.push_back(p[i].expert_id);auto result=chronological_routes(ids);transitions.finish(cache,epoch,true);active=false;return result;}
 void committed(){need(transitions.phase()==CacheTransition::Phase::idle&&!active&&!transitions.poisoned()&&device.in_flight()==0,"p213 update commit boundary");verify();}
 uint64_t begin_position(){need(!active,"p213 ordinary begin during chunk");return transitions.begin(cache);}
 void finish_position(uint64_t value,bool complete){need(!active,"p213 ordinary finish during chunk");transitions.finish(cache,value,complete);}
 p58::Plan prepare_update(const std::vector<uint32_t>& routes){need(!active,"p213 prepare during chunk");return transitions.prepare(cache,routes);}
 void commit_update(uint64_t value,bool copies_complete,bool publication_complete){need(!active,"p213 commit during chunk");transitions.commit(cache,value,copies_complete,publication_complete);}
 void close_after_drain(){need(copies.empty()&&device.in_flight()==0,"p213 close before completion");need(transitions.close(cache,true),"p213 cache retained");active=false;}
};
} // namespace p213
