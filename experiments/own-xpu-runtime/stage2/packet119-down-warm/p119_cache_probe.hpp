#pragma once
// Coordinator-only device cache diagnostic; inclusion/compilation opens no device.
// Runtime cache metadata is not a measurement of usable L2 capacity. The timed
// probe reads one uint32 per 64-byte line and stores a live checksum per worker.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>
namespace p119_cache {
inline void probe(sycl::queue& q, void (*guard)() = nullptr) {
 constexpr size_t mib=1024*1024,scrub_bytes=512*mib,max_bytes=64*mib;
 constexpr size_t stride=64,workers=65536;
 constexpr size_t allocation_bytes=scrub_bytes+max_bytes+workers*sizeof(uint32_t);
 static_assert(allocation_bytes<=600*mib);
 struct Memory {
  sycl::queue& q;std::vector<void*> pointers;
  ~Memory(){try{q.wait_and_throw();}catch(...){}for(auto p:pointers)sycl::free(p,q);}
  uint32_t* alloc(size_t n){auto p=sycl::malloc_device<uint32_t>(n/4,q);if(!p)throw std::bad_alloc();pointers.push_back(p);return p;}
 } memory{q,{}};
 if(guard)guard();
 const auto device=q.get_device();
 const auto reported=device.get_info<sycl::info::device::global_mem_cache_size>();
 const auto line=device.get_info<sycl::info::device::global_mem_cache_line_size>();
 std::cout<<"{\"kind\":\"cache_device\",\"runtime_reported_global_cache_bytes\":"<<reported
  <<",\"runtime_reported_cache_line_bytes\":"<<line
  <<",\"probe_stride_bytes\":64,\"scrub_bytes\":"<<scrub_bytes
  <<",\"allocation_bytes\":"<<allocation_bytes
  <<",\"capacity_measurement\":false,\"reported_cache_level\":\"unspecified_SYCL_global_mem_cache\",\"diagnostic_only\":true}\n";
 auto* scrub=memory.alloc(scrub_bytes);auto* data=memory.alloc(max_bytes);auto* sink=memory.alloc(workers*4);
 // Initialization has no role in the timing. The scrub is an actual compute
 // read of every 64-byte line; a transfer-engine memset alone is not eviction.
 q.parallel_for(sycl::range<1>(workers),[=](sycl::id<1> item){
  for(size_t i=item[0];i<scrub_bytes/4;i+=workers)scrub[i]=uint32_t(i*1664525u+1013904223u);
  for(size_t i=item[0];i<max_bytes/4;i+=workers)data[i]=uint32_t(i*22695477u+119u);
 }).wait_and_throw();
 auto read=[&](uint32_t* source,size_t bytes){
  const size_t lines=bytes/stride,n=std::min(workers,lines);
  return q.parallel_for(sycl::range<1>(n),[=](sycl::id<1> item){
   uint32_t sum=0;for(size_t i=item[0];i<lines;i+=n)sum^=source[i*(stride/4)];
   sink[item[0]]=sum;
  });
 };
 auto ns=[](const sycl::event& e){return e.get_profiling_info<sycl::info::event_profiling::command_end>()-e.get_profiling_info<sycl::info::event_profiling::command_start>();};
 for(size_t size_mib:{1u,2u,4u,8u,16u,24u,32u,48u,64u})for(unsigned rep=0;rep<8;++rep){
  if(guard)guard();
  read(scrub,scrub_bytes).wait_and_throw();
  auto cold=read(data,size_mib*mib);cold.wait_and_throw();
  auto warm=read(data,size_mib*mib);warm.wait_and_throw();
  uint32_t checksum=0;q.memcpy(&checksum,sink,4).wait_and_throw();
  std::cout<<"{\"kind\":\"cache_probe\",\"bytes\":"<<size_mib*mib
   <<",\"repeat\":"<<rep<<",\"repetitions\":8,\"cold_ns\":"<<ns(cold)<<",\"warm_ns\":"<<ns(warm)
   <<",\"scrub_bytes\":"<<scrub_bytes<<",\"stride_bytes\":64,\"sink0\":"<<checksum
   <<",\"useful_read_bytes\":"<<size_mib*mib/16
   <<",\"footprint_is_address_span\":true,\"diagnostic_only\":true}\n";
 }
 q.wait_and_throw();if(guard)guard();std::cout<<std::flush;
}
}
