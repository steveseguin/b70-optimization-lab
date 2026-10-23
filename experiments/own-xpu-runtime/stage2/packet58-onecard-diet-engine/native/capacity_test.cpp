#include "cache_table.hpp"
#include <array>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <iostream>
static unsigned checks=0,negatives=0;
static void check(bool ok){if(!ok)throw std::runtime_error("capacity byte gate");++checks;}
static void refuses(const std::function<void()>& f){bool no=false;try{f();}catch(const std::logic_error&){no=true;}check(no);++negatives;}
int main(){
  std::vector<std::array<unsigned char,256>> host(24);
  std::vector<p58::Expert> experts;
  for(size_t i=0;i<host.size();++i){for(size_t j=0;j<256;++j)host[i][j]=(i*31+j*17)%251;
    auto p=uint64_t(host[i].data());experts.push_back({p,p+64,p+160,64,96,96});}
  auto* allocation=static_cast<unsigned char*>(std::aligned_alloc(256,4096));check(allocation);
  std::memset(allocation,0,4096);p58::Cache cache(experts,uint64_t(allocation),4096);
  size_t mixed=0,above_control=0;uint64_t previous_epoch=0;
  for(unsigned view=0;view<5;++view){
    const uint64_t cap=view%2?4096:2048;
    cache.reset_capacity(cap);check(cache.capacity()==cap&&cache.resident_bytes()==0);
    for(size_t i=0;i<host.size();++i)check(cache.table()[i].gate==uint64_t(host[i].data()));
    for(unsigned step=0;step<40;++step){
      auto epoch=cache.begin_position();check(epoch>previous_epoch);previous_epoch=epoch;
      refuses([&]{cache.reset_capacity(cap);});
      for(size_t i=0;i<host.size();++i){const auto& e=cache.table()[i];
        check(!std::memcmp(reinterpret_cast<void*>(e.gate),host[i].data(),64));
        check(!std::memcmp(reinterpret_cast<void*>(e.up),host[i].data()+64,96));
        check(!std::memcmp(reinterpret_cast<void*>(e.down),host[i].data()+160,96));
        if(cache.resident(i))++mixed;
      }
      cache.finish_position(epoch,true);
      auto plan=cache.prepare({step%24,(step+3)%24,(step+7)%24});
      refuses([&]{cache.reset_capacity(cap);});
      for(const auto& f:plan.fills){check(f.offset+f.bytes<=cap);if(f.offset>=2048)++above_control;
        std::memcpy(allocation+f.offset,host[f.expert].data(),256);}
      cache.commit(plan.epoch,true,true);check(cache.resident_bytes()<=cap);
    }
  }
  refuses([&]{cache.reset_capacity(4352);});refuses([&]{cache.reset_capacity(4095);});
  check(mixed&&above_control);std::free(allocation);
  std::cout<<"{\"passed\":true,\"device_executed\":false,\"capacity_switches\":5,\"checks\":"<<checks
           <<",\"negative_checks\":"<<negatives<<",\"mixed_source_observations\":"<<mixed
           <<",\"fills_above_control_extent\":"<<above_control<<"}\n";
}
