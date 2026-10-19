#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/build/native/p60_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/build/native/p60_kernels.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait/build/native/p73_hc.hpp"
namespace p60 {
inline Bound bind(std::span<void*const> p,unsigned capacity) {
 return {static_cast<uint16_t*>(p[0]),static_cast<float*>(p[1]),
  static_cast<uint8_t*>(p[2]),static_cast<uint8_t*>(p[3]),static_cast<uint8_t*>(p[4]),
  static_cast<uint16_t*>(p[5]),static_cast<uint16_t*>(p[6]),static_cast<uint16_t*>(p[7]),
  static_cast<uint16_t*>(p[8]),static_cast<uint16_t*>(p[9]),static_cast<uint16_t*>(p[10]),
  static_cast<float*>(p[11]),static_cast<float*>(p[12]),static_cast<uint32_t*>(p[13]),
  static_cast<uint32_t*>(p[14]),static_cast<uint32_t*>(p[15]),capacity};
}
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
template<int Stage,bool Wide=false>struct Kernel final:Base {
 unsigned capacity;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  auto b=bind(p,capacity);
  if constexpr(Stage==0)host_norm(b);
  if constexpr(Stage==1)host_low_inject(b);
  if constexpr(Stage==2){if constexpr(Wide)p73hc::host(b);else host_gate_mix(b);}
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto b=bind(p,capacity);
  if constexpr(Stage==0)return norm_kernel(q,b,deps);
  if constexpr(Stage==1)return low_inject_kernel(q,b,deps);
  if constexpr(Stage==2){if constexpr(Wide)return p73hc::device(q,b,deps);else return gate_mix_kernel(q,b,deps);}
 }
#endif
};
template<int Stage,bool Wide=false>integrated::Launch issue(ownrt::Device&d,const IDs&ids,unsigned capacity) {
 Kernel<Stage,Wide> op;op.capacity=capacity;auto e=d.compute(op,ids,{});return {e,e,1};
}
integrated::Launch submit(ownrt::Device&d,const IDs&ids,int stage,unsigned capacity,bool wide) {
 if(!capacity||capacity>4096)throw std::invalid_argument("packet60 capacity");
 const std::array<size_t,16> bytes{K*2,K*4,L*iq3::expanded::row_bytes(Type::Q8_0,K),
  K*iq3::expanded::row_bytes(Type::Q8_0,L),S*K*4,K*2,L*2,L*2,K*2,H*2,S*2,320*4,32*4,4,4,4};
 for(unsigned i=0;i<ids.size();++i){const auto&r=d.arena.row(ids[i]);
  unsigned align=(i==0||(i>=5&&i<=10))?2:4;
  if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<bytes[i]||uintptr_t(r.pointer)%align)
   throw std::invalid_argument("packet60 lifetime/extent/alignment");
  for(unsigned j=0;j<i;++j)if(ids[i]==ids[j])throw std::invalid_argument("packet60 binding alias");
 }
 switch(stage){case 0:return issue<0>(d,ids,capacity);case 1:return issue<1>(d,ids,capacity);case 2:return wide?issue<2,true>(d,ids,capacity):issue<2>(d,ids,capacity);}
 throw std::invalid_argument("packet60 stage");
}
}
