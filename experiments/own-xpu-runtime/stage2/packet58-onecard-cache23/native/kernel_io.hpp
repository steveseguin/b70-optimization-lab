#pragma once
// Packet176: process-wide copy-engine-free foreground token I/O
// (default copy = packet58as). Set only by the owner thread at a drained view
// boundary. Both operations are ordinary compute-queue kernels submitted
// through Device::compute (device-only bindings; the pinned host pointers are
// immutable kernel-argument values, as in p58v::Publish). Neither issues a
// memory-copy command, so no runtime copy offload can route them to a copy
// engine, and neither depends on any copy-engine event.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-cache23/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner.hpp"
#include <array>
#include <cstdint>
#include <cstring>
#ifdef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-cache23/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/adapter.hpp"
#else
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-cache23/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p176 {
inline thread_local bool kernel_io=false;
constexpr size_t tail_record_bytes=16;   // slab[0] + 0: status u32, token i32, stamp u64
constexpr size_t head_offset=4096;       // slab[0] + 4096: staged head bytes
constexpr size_t head_capacity=4*1024*1024-head_offset;
constexpr size_t max_head_items=8;
constexpr size_t max_route_layers=48;
// Bindings: p[0]=error, p[1]=next_token, p[2..2+layers)=route sources (device).
#ifdef OWN_RT_HOST_ONLY
struct TailStore final : integrated::HostOperation {
  uint8_t* host;uint8_t* routes;uint32_t layers,route_bytes;uint64_t stamp;
  TailStore(uint8_t* h,uint8_t* r,uint32_t l,uint32_t n,uint64_t s):host(h),routes(r),layers(l),route_bytes(n),stamp(s){}
  void run(std::span<void*const> p)const override {
    for(uint32_t i=0;i<layers;++i)std::memcpy(routes+size_t(i)*route_bytes,p[2+i],route_bytes);
    std::memcpy(host,p[0],4);std::memcpy(host+4,p[1],4);std::memcpy(host+8,&stamp,8);
  }
};
struct HeadLoad final : integrated::HostOperation {
  const uint8_t* host;std::array<uint32_t,max_head_items> offset{},bytes{};uint32_t items,total;
  HeadLoad(const uint8_t* h,std::array<uint32_t,max_head_items> o,std::array<uint32_t,max_head_items> b,uint32_t n,uint32_t t):host(h),offset(o),bytes(b),items(n),total(t){}
  void run(std::span<void*const> p)const override {
    for(uint32_t k=0;k<items;++k)std::memcpy(p[k],host+offset[k],bytes[k]);
  }
};
#else
struct TailStore final : ownrt::SyclOperation {
  uint8_t* host;uint8_t* routes;uint32_t layers,route_bytes;uint64_t stamp;
  TailStore(uint8_t* h,uint8_t* r,uint32_t l,uint32_t n,uint64_t s):host(h),routes(r),layers(l),route_bytes(n),stamp(s){}
  sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
    std::array<const uint8_t*,max_route_layers> source{};
    for(uint32_t i=0;i<layers;++i)source[i]=static_cast<const uint8_t*>(p[2+i]);
    auto* error=static_cast<const uint32_t*>(p[0]);auto* token=static_cast<const uint32_t*>(p[1]);
    auto* h=host;auto* r=routes;const size_t n=route_bytes,count=size_t(layers)*route_bytes;const uint64_t s=stamp;
    // One work-item per route byte plus one record item; all stores target
    // USM host memory and become host-visible when this kernel's event completes.
    return q.submit([&](sycl::handler& cgh){cgh.depends_on(deps);
      cgh.parallel_for(sycl::range<1>(count+1),[=](sycl::id<1> id){const size_t i=id[0];
        if(i==count){auto* w=reinterpret_cast<uint32_t*>(h);w[0]=error[0];w[1]=token[0];*reinterpret_cast<uint64_t*>(h+8)=s;}
        else r[i]=source[i/n][i%n];});});
  }
};
struct HeadLoad final : ownrt::SyclOperation {
  const uint8_t* host;std::array<uint32_t,max_head_items> offset{},bytes{};uint32_t items,total;
  HeadLoad(const uint8_t* h,std::array<uint32_t,max_head_items> o,std::array<uint32_t,max_head_items> b,uint32_t n,uint32_t t):host(h),offset(o),bytes(b),items(n),total(t){}
  sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
    std::array<uint8_t*,max_head_items> dest{};for(uint32_t k=0;k<items;++k)dest[k]=static_cast<uint8_t*>(p[k]);
    auto* h=host;auto o=offset;auto b=bytes;const uint32_t n=items;
    // Staged items are contiguous: item k covers [o[k], o[k]+b[k]) of the staging.
    return q.submit([&](sycl::handler& cgh){cgh.depends_on(deps);
      cgh.parallel_for(sycl::range<1>(total),[=](sycl::id<1> id){const uint32_t i=uint32_t(id[0]);uint32_t k=0;
        while(k+1<n&&i>=o[k+1])++k;dest[k][i-o[k]]=h[i];});});
  }
};
#endif
}
