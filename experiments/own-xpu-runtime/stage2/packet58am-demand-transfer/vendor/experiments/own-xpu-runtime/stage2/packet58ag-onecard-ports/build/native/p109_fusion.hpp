#pragma once
// Concrete K640 Q8 shared-down plus the two existing elementwise tails.
// No generic descriptor interpreter runs on the device.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/build/native/p109_route.hpp"
namespace p109 {
struct TailBound {
 const uint8_t* weight;const uint16_t* input;uint16_t* down;
 const uint16_t* experts;const float* probabilities;uint16_t* mixture;
 const uint16_t* gate;const float* one;uint16_t* output;
 uint32_t *error;const uint32_t *position,*active;unsigned capacity;
};
inline TailBound bind(std::span<void*const> p,unsigned capacity){
 return {static_cast<const uint8_t*>(p[0]),static_cast<const uint16_t*>(p[1]),static_cast<uint16_t*>(p[2]),
  static_cast<const uint16_t*>(p[3]),static_cast<const float*>(p[4]),static_cast<uint16_t*>(p[5]),
  static_cast<const uint16_t*>(p[6]),static_cast<const float*>(p[7]),static_cast<uint16_t*>(p[8]),
  static_cast<uint32_t*>(p[9]),static_cast<const uint32_t*>(p[10]),static_cast<const uint32_t*>(p[11]),capacity};
}
inline uint32_t failed(TailBound b){
#ifdef OWN_RT_HOST_ONLY
 return *b.error;
#else
 return sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).load();
#endif
}
inline void fail(TailBound b){
#ifdef OWN_RT_HOST_ONLY
 *b.error=1;
#else
 sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).store(1);
#endif
}
inline void tail(TailBound b,unsigned row,float down){
 // These two production writers are unconditional, even on inactive/error paths.
 b.down[row]=iq3::bf16_bits(down);
 b.mixture[row]=iq3::bf16_bits(iq3::kopt4::combine(b.experts,b.probabilities,2560,row));
 if(!*b.active||failed(b))return;
 int32_t pos=std::bit_cast<int32_t>(*b.position);
 if(pos<0||unsigned(pos)>=b.capacity){if(!row)fail(b);return;}
 // Keep +0, runtime *one, the extra BF16 round, and the separate shared round.
 float sum=0;sum=sum+iq3::bits_float(uint32_t(b.mixture[row])<<16)*b.one[0];
 // Device/Intel expression: retain the original operation and rounding order.
 b.output[row]=ng::Args::bits(ng::Args::bf(sum)+ng::Args::bf(iq3::bits_float(uint32_t(b.down[row])<<16)*ng::sigmoid(iq3::bits_float(uint32_t(b.gate[0])<<16))));
}
#if defined(OWN_RT_HOST_ONLY) && defined(__GNUC__) && !defined(__clang__)
// GNU's O3 CPU loop vectorization changes NaN payload operand selection.
// Preserve its original complete loop in the CPU backend. This is not the
// device implementation and does not add a device launch or interpreter.
__attribute__((noinline,noclone)) inline void host_blend_generic(ng::Shape shape,ng::Args args){ng::cpu(shape,args);}
inline void host_blend(TailBound b){
 ng::Shape s{};s.op=ng::moe_combine;s.width=2560;s.extra=1;s.capacity=b.capacity;
 ng::Args a{};a.p[0]=b.mixture;a.p[1]=const_cast<float*>(b.one);a.p[2]=b.down;a.p[3]=const_cast<uint16_t*>(b.gate);a.p[4]=b.output;
 a.p[15]=b.error;a.p[17]=const_cast<uint32_t*>(b.position);a.p[18]=const_cast<uint32_t*>(b.active);host_blend_generic(s,a);
}
#endif
struct SharedDown final:p49c::Base {
 unsigned capacity;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  auto b=bind(p,capacity);
  for(unsigned row=0;row<2560;++row){float sums[32]{};
   for(unsigned lane=0;lane<32;++lane)sums[lane]=p33::dense_lane<iq3::Type::Q8_0,640>(b.weight+row*760,b.input,0,640,lane);
#if defined(__GNUC__) && !defined(__clang__)
   b.down[row]=iq3::bf16_bits(iq3::tree32(sums));
   b.mixture[row]=iq3::bf16_bits(iq3::kopt4::combine(b.experts,b.probabilities,2560,row));
#else
   tail(b,row,iq3::tree32(sums));
#endif
  }
#if defined(__GNUC__) && !defined(__clang__)
  host_blend(b);
#endif
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto b=bind(p,capacity);const sycl::nd_range<1> range(2560*32,32);
  return ownrt::prepared_submit(q,[=](sycl::handler& h){h.depends_on(deps);
   h.parallel_for(range,packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),row=it.get_group_linear_id();
    float value=p33::dense_lane<iq3::Type::Q8_0,640>(b.weight+row*760,b.input,0,640,lane);
    for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(lane%(2*width)==0)value=value+rhs;}
    if(!lane)tail(b,row,value);
   }));
  });
 }
#endif
};
template<size_t N>inline void validate(ownrt::Device& d,const std::array<ownrt::Allocation,N>& ids,const std::array<size_t,N>& extents,const std::array<unsigned,N>& align){
 for(size_t i=0;i<N;++i){const auto&r=d.arena.row(ids[i]);
  if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<extents[i]||uintptr_t(r.pointer)%align[i])throw std::invalid_argument("p109 allocation extent/alignment/lifetime");
  for(size_t j=0;j<i;++j){const auto&s=d.arena.row(ids[j]);auto a=uintptr_t(r.pointer),b=uintptr_t(s.pointer);
   if(a<b+extents[j]&&b<a+extents[i])throw std::invalid_argument("p109 binding alias");}
 }
}
inline integrated::Launch shared_down(ownrt::Device& d,const std::array<ownrt::Allocation,12>& ids,unsigned capacity){
 if(!capacity||capacity>INT32_MAX)throw std::invalid_argument("p109 capacity");
 if(integrated::arithmetic::row_bytes(iq3::Type::Q8_0,640,6)!=760)throw std::logic_error("p109 production shared-down stride");
 validate(d,ids,std::array<size_t,12>{2560*760,1280,5120,51200,40,5120,2,4,5120,4,4,4},std::array<unsigned,12>{1,2,2,2,4,2,2,4,2,4,4,4});
 SharedDown k;k.capacity=capacity;auto e=d.compute(k,ids,{});return {e,e,1};
}
inline integrated::Launch route_activation(ownrt::Device& d,const integrated::Spec& s,std::span<const ownrt::Allocation> ids,const std::array<ownrt::Allocation,3>& activation){
 p49droute::validate(d,s,ids);
 validate(d,activation,std::array<size_t,3>{1280,1280,1280},std::array<unsigned,3>{2,2,2});
 for(auto a:activation)for(auto b:ids)if(a==b)throw std::invalid_argument("p109 route/activation alias");
 std::vector<ownrt::Allocation> all(ids.begin(),ids.end());all.insert(all.end(),activation.begin(),activation.end());
 p109route::Kernel k;k.spec=s;auto e=d.compute(k,all,{});return {e,e,1};
}
}
