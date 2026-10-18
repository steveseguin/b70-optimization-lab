#pragma once
#ifndef OWN_RT_HOST_ONLY
// Standalone tracked reads, outside graph capture. One volatile byte per cache
// line, all lines, bounded output. Does not alter any model allocation.
struct P141Touch final : ownrt::SyclOperation {
 size_t offset=0, bytes=0;
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>&deps)const override {
  const auto* src=static_cast<const uint8_t*>(p[0])+offset;
  auto* out=static_cast<uint32_t*>(p[1]);size_t n=bytes;
  return q.submit([=](sycl::handler&h){h.depends_on(deps);
   h.parallel_for(sycl::range<1>((n+4095)/4096),[=](sycl::id<1> id){
    size_t start=size_t(id[0])*4096;uint32_t sum=0;
    for(size_t k=start;k<sycl::min(start+4096,n);k+=64)sum+=static_cast<const volatile uint8_t*>(src)[k];
    out[id[0]]=sum;
   });
  });
 }
};
#endif
