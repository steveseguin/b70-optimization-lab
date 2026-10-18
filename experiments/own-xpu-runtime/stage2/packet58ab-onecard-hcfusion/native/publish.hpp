#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner.hpp"
#include <array>
#ifdef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/adapter.hpp"
#else
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p58v {
// One contiguous H2D upload, then a device scatter into unchanged table handles.
// The 144 destinations are immutable pointer values in the kernel argument.
#ifdef OWN_RT_HOST_ONLY
struct Publish final : integrated::HostOperation {
  std::array<uint64_t*,144> tables;size_t words;const void* host;
  Publish(std::array<uint64_t*,144> t,size_t w,const void* h):tables(t),words(w),host(h){}
  void run(std::span<void*const> p)const override {
    std::memcpy(p[0],host,144*words*sizeof(uint64_t));
    for(size_t i=0;i<144;++i)std::memcpy(tables[i],static_cast<uint64_t*>(p[0])+i*words,words*sizeof(uint64_t));
  }
};
#else
struct Publish final : ownrt::SyclOperation {
  std::array<uint64_t*,144> tables;size_t words;const void* host;
  Publish(std::array<uint64_t*,144> t,size_t w,const void* h):tables(t),words(w),host(h){}
  sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
    auto* data=static_cast<uint64_t*>(p[0]);auto dest=tables;auto count=words;
    // Use the foreground queue so a long BCS fill cannot hold publication behind it.
    auto uploaded=q.memcpy(data,host,144*count*sizeof(uint64_t),deps);
    return q.submit([&](sycl::handler& h){h.depends_on(uploaded);
      h.parallel_for(sycl::range<1>(144*count),[=](sycl::id<1> i){auto k=i[0];dest[k/count][k%count]=data[k];});});
  }
};
#endif
}
