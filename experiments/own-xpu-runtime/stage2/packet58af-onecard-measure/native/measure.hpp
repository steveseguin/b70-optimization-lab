#pragma once
#include <array>
#include <chrono>
#include <cstdint>
#include <ostream>
#include <stdexcept>
#include <vector>
#ifndef OWN_RT_HOST_ONLY
#include <sycl/sycl.hpp>
#endif
namespace p58af {
inline thread_local int arm=0,sample_layer=0;
inline thread_local bool token=false;
inline bool active(){return arm&&token;}
struct Layer {uint64_t hits=0,misses=0,hit_bytes=0,miss_bytes=0;};
inline thread_local std::array<Layer,48> layers{};
inline thread_local double pack_ms=0,wait_ms=0,boundary_ms=0;
inline thread_local unsigned publications=0;
struct Backend {virtual ~Backend()=default;virtual void profiling(bool)=0;virtual void retain(uint64_t,int,int)=0;};
#ifndef OWN_RT_HOST_ONLY
struct Sample {sycl::event event;int layer,projection,partition;};
inline thread_local std::vector<Sample> samples;
inline void retain(sycl::event event,int layer,int projection,int partition=0){
  if(samples.size()>=128)throw std::runtime_error("bounded measurement event count");
  samples.push_back({event,layer,projection,partition});
}
#endif
inline void begin(int generated_index){
  token=arm!=0&&generated_index>0;sample_layer=(generated_index-1)%48;pack_ms=wait_ms=boundary_ms=0;publications=0;layers={};
#ifndef OWN_RT_HOST_ONLY
  samples.clear();if(samples.capacity()<128)samples.reserve(128);
#endif
}
inline void finish(std::ostream& out,int index,int token_id,int position){
  if(!active())return;
  token=false;out.precision(17);
  out<<"{\"schema\":\"packet58af.token.v1\",\"arm\":"<<arm<<",\"generated_index\":"<<index<<",\"token_id\":"<<token_id<<",\"position\":"<<position
     <<",\"sample_layer\":"<<sample_layer<<",\"pack_ms\":"<<pack_ms<<",\"publication_wait_ms\":"<<wait_ms<<",\"publication_boundary_ms\":"<<boundary_ms<<",\"publications\":"<<publications<<",\"events\":[";
#ifndef OWN_RT_HOST_ONLY
  bool comma=false;for(const auto& s:samples){
    // The existing token drain already completed these events. Never wait here.
    if(s.event.get_info<sycl::info::event::command_execution_status>()!=sycl::info::event_command_status::complete)throw std::runtime_error("measurement before existing drain");
    auto start=s.event.get_profiling_info<sycl::info::event_profiling::command_start>();
    auto end=s.event.get_profiling_info<sycl::info::event_profiling::command_end>();
    if(!start||end<start)throw std::runtime_error("invalid device measurement interval");
    out<<(comma?",":"")<<"{\"layer\":"<<s.layer<<",\"projection\":"<<s.projection<<",\"partition\":"<<s.partition<<",\"start_ns\":"<<start<<",\"end_ns\":"<<end<<"}";comma=true;
  }samples.clear();
#endif
  out<<"],\"layers\":[";for(unsigned i=0;i<48;++i){const auto& l=layers[i];out<<(i?",":"")<<"{\"layer\":"<<i<<",\"hits\":"<<l.hits<<",\"misses\":"<<l.misses<<",\"hit_bytes\":"<<l.hit_bytes<<",\"miss_bytes\":"<<l.miss_bytes<<"}";}
  out<<"],\"extra_waits\":0}\n";
}
}
