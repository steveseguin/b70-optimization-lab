// Packet188 kernel foreground I/O on two cards (packet176's one-card lever, selection key kernel_io=kernel).
//
// A KioCopy moves at most `width` byte ranges with one ordinary compute-queue kernel. Endpoints are raw
// pointers captured as immutable kernel-argument values: device allocations (bound through Device::compute,
// which requires live device bindings) and the engine's pinned USM-host staging ("kernel-io"). The kernel
// issues no memory-copy command, so no runtime copy offload can route it to a copy engine, and it carries
// no arithmetic: every byte is stored unchanged (the HOST_ONLY form is a plain memcpy per range).
// Ordering is the in-order compute queue: a KioCopy runs after every previously submitted command and
// before every later one, exactly like the CopyEngine copy it replaces.
#pragma once
#include <array>
#include <cstdint>
#include <cstring>
#include <span>
#include <vector>
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
namespace p188 {
#ifdef OWN_RT_HOST_ONLY
struct KioCopy final : integrated::HostOperation {
#else
struct KioCopy final : ownrt::SyclOperation {
#endif
 struct Item { uint8_t* dst=nullptr; const uint8_t* src=nullptr; uint32_t bytes=0, start=0; };
 static constexpr size_t width=8;
 std::array<Item,width> items{}; uint32_t count=0, total=0;
 void add(void* dst,const void* src,size_t bytes){
  if(count>=width||bytes==0||bytes>(1u<<24)||total+bytes>(1u<<24))throw std::invalid_argument("packet188 KioCopy extent/width");
  items[count]={static_cast<uint8_t*>(dst),static_cast<const uint8_t*>(src),uint32_t(bytes),total};total+=uint32_t(bytes);++count;
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>) const override {
  for(uint32_t i=0;i<count;++i)std::memcpy(items[i].dst,items[i].src,items[i].bytes);
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const>,const std::vector<sycl::event>&) const override {
  auto values=items;const uint32_t n=count,t=total;
  // One work-item per byte; ranges are contiguous in the flattened index space (item k covers
  // [start_k, start_k+bytes_k)). Sizes are bounded by the staging capacity (<= 16 MiB, 64 KiB typical).
  return ownrt::prepared_submit(q,[=,range=sycl::range<1>(t)](sycl::handler& h){
   h.parallel_for(range,packet26::checked([=](sycl::id<1> id){
    const uint32_t i=uint32_t(id[0]);uint32_t k=0;
    while(k+1<n&&i>=values[k+1].start)++k;
    values[k].dst[i-values[k].start]=values[k].src[i-values[k].start];
   }));
  });
 }
#endif
};
// Staging layout of the per-rank pinned "kernel-io" allocation (bytes).
constexpr size_t position_slot=0, token_history_slot=64, history_bytes=16;
constexpr size_t sync_offset=4096, sync_capacity=64*1024;
constexpr size_t stage_offset=sync_offset+sync_capacity;
}
