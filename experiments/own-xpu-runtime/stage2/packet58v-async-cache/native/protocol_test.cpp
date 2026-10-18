#include "cache_protocol.hpp"
#include "publish.hpp"
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <functional>
static unsigned negatives=0,checks=0;
static void check(bool b){if(!b)throw std::runtime_error("protocol byte/race check failed");++checks;}
static void refuses(const std::function<void()>& f){bool no=false;try{f();}catch(const std::logic_error&){no=true;}check(no);++negatives;}
int main(){
  std::vector<std::array<unsigned char,256>> host(8);
  std::vector<p58::Expert> experts;
  for(size_t i=0;i<host.size();++i){for(size_t j=0;j<256;++j)host[i][j]=(i*31+j*17)%251;
    auto p=uint64_t(host[i].data());experts.push_back({p,p+64,p+160,64,96,96});}
  auto* device=static_cast<unsigned char*>(std::aligned_alloc(256,512));
  check(device!=nullptr);std::memset(device,0,512);
  p58::Cache cache(experts,uint64_t(device),512);p58v::Protocol protocol;
  auto visible=cache.table();size_t copies=0,host_rows=0,device_rows=0,same_slot=0;
  uint64_t last_offset=~uint64_t(0);
  auto equal=[&]{for(size_t i=0;i<host.size();++i){const auto& row=visible[i];
    check(!std::memcmp(reinterpret_cast<void*>(row.gate),host[i].data(),64));
    check(!std::memcmp(reinterpret_cast<void*>(row.up),host[i].data()+64,96));
    check(!std::memcmp(reinterpret_cast<void*>(row.down),host[i].data()+160,96));
    (row.gate==experts[i].host_gate?host_rows:device_rows)++;}};
  for(unsigned round=0;round<48;++round){
    // Actual native code plans AFTER enqueue while the current position owns the old table.
    protocol.begin();equal();protocol.prepare(cache,{round%8,(round+1)%8});
    refuses([&]{protocol.revoked(cache);});
    refuses([&]{protocol.submitted(true,round+1);});
    refuses([&]{protocol.end(false);});
    // The old table is still valid while the plan is merely CPU metadata.
    equal();protocol.end(true);visible=protocol.revoked(cache);
    refuses([&]{protocol.submitted(false,round+1);});
    equal();protocol.submitted(true,round+1);
    refuses([&]{protocol.commit(cache,false,true);});
    refuses([&]{protocol.prepare(cache,{7});});
    // Delayed completion: two complete positions use the revoked table.
    for(int delay=0;delay<2;++delay){protocol.begin();equal();check(!protocol.may_publish(false));protocol.end(true);}
    // Fill completes in the middle of a position. It cannot change visible pointers.
    protocol.begin();auto before=visible;
    for(const auto& fill:protocol.plan->fills){
      // Every public device range must be disjoint from the destination being overwritten.
      for(const auto& row:visible)for(auto ptr:{row.gate,row.up,row.down})
        check(ptr<uint64_t(device)+fill.offset||ptr>=uint64_t(device)+fill.offset+fill.bytes);
      if(fill.offset==last_offset)++same_slot;last_offset=fill.offset;
      auto id=fill.expert;std::memcpy(device+fill.offset,host[id].data(),256);++copies;
    }
    check(!protocol.may_publish(true));refuses([&]{protocol.commit(cache,true,true);});
    equal();check(!std::memcmp(before.data(),visible.data(),visible.size()*sizeof(p58::Entry)));
    protocol.end(true);check(protocol.may_publish(true));
    refuses([&]{protocol.commit(cache,true,false);});
    visible=protocol.plan->table;protocol.commit(cache,true,true);equal();
    check(cache.resident_bytes()<=512);
  }
  check(host_rows&&device_rows&&copies>40);
  // LRU sees accesses during a pending fill, rather than ignoring that position.
  p58::Cache lru(experts,uint64_t(device),512);
  auto seed=lru.prepare({0,1});lru.commit(seed.epoch,true,true);
  lru.observe({0});auto next=lru.prepare({2});
  check(next.table[0].gate!=experts[0].host_gate&&next.table[1].gate==experts[1].host_gate);
  lru.observe({0});lru.commit(next.epoch,true,true);next=lru.prepare({1});
  check(next.table[0].gate!=experts[0].host_gate&&next.table[2].gate==experts[2].host_gate);
  lru.commit(next.epoch,true,true);
  // Full publication shape: all 144 tables, 512 pointer+generation rows.
  std::vector<uint64_t> source(144*1024),staging(source.size()),tables(source.size());
  std::array<uint64_t*,144> destinations{};
  for(size_t i=0;i<source.size();++i)source[i]=0xc001cafe00000000ull+i*17;
  for(size_t i=0;i<144;++i)destinations[i]=tables.data()+i*1024;
  p58v::Publish publish(destinations,1024,source.data());std::array<void*,1> args{staging.data()};publish.run(args);
  check(tables==source&&staging==source);
  std::free(device);
  std::cout<<"{\"passed\":true,\"device_executed\":false,\"checks\":"<<checks<<",\"race_refusals\":"<<negatives
           <<",\"fills\":"<<copies<<",\"host_rows\":"<<host_rows<<",\"device_rows\":"<<device_rows
           <<",\"publication_rows\":73728,\"zero_copy_mixed_streamed_bytes_equal\":true,\"delayed_copy\":true,\"mid_position_completion\":true,\"repeated_slot_evictions\":true}\n";
}
