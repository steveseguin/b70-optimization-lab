#pragma once
#include "selected.hpp"
#include <string_view>

// Unwired diagnostic source. Caller must retain the normal BF16 argmax and
// prove BF16 state/token equality against5926 before interpreting this sidecar.
namespace head_observation {
inline constexpr unsigned rows=248320, columns=2560, row_bytes=3380;
inline constexpr size_t weights_bytes=size_t(rows)*row_bytes;
inline constexpr size_t observation_bytes=size_t(rows)*sizeof(float);
struct Bound {
 const uint8_t* w{};const uint16_t* x{};uint16_t* y{};float* observation{};
};
struct DualStore final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 Bound bind(std::span<void*const> p)const {
  return {static_cast<const uint8_t*>(p[0]),static_cast<const uint16_t*>(p[1]),
          static_cast<uint16_t*>(p[2]),static_cast<float*>(p[3])};
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  const auto d=bind(p);
  for(unsigned row=0;row<rows;++row){
   float sums[32]{};
   for(unsigned lane=0;lane<32;++lane)
    sums[lane]=p33::dense_lane<iq3::Type::Q6_K,columns>(d.w+row*row_bytes,d.x,0,columns,lane);
   float v=iq3::tree32(sums);
   d.observation[row]=v;
   d.y[row]=iq3::bf16_bits(v);
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  const auto d=bind(p);
  return ownrt::prepared_submit(q,[=,r=sycl::nd_range<1>(size_t(rows)*32,32)](sycl::handler& h){
   h.parallel_for(r,p28::checked(packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),row=unsigned(it.get_group_linear_id());
    float sum=p33::dense_lane<iq3::Type::Q6_K,columns>(d.w+row*row_bytes,d.x,0,columns,lane);
    for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    if(lane==0){float v=sum;d.observation[row]=v;d.y[row]=iq3::bf16_bits(v);}
   })));
  });
 }
#endif
};
inline integrated::Launch submit(ownrt::Device& d,const integrated::Matrix& m,
 ownrt::Allocation observation,std::string_view weight_name,unsigned variant){
 if(weight_name!="output.weight"||variant!=6||m.type!=iq3::Type::Q6_K||
    m.rows!=rows||m.columns!=columns||m.count!=1||m.experts!=1||
    m.span!=rows||m.routes||m.status||m.fp32||
    m.activation!=iq3::Type::BF16||m.output_type!=iq3::Type::BF16)
  throw std::invalid_argument("head observation exact selected matrix");
 // Original admission, including live input/output/workspace and alias rules.
 p28::validate(d,{m},"p28.dense.wg32",false,6);
 const auto& w=d.arena.row(m.w);const auto& o=d.arena.row(observation);
 if(w.bytes!=weights_bytes||!o.live||o.memory!=ownrt::Memory::device||
    o.bytes!=observation_bytes||reinterpret_cast<uintptr_t>(o.pointer)%16)
  throw std::invalid_argument("head observation storage/extent/alignment");
 iq3::kopt3::validate_aliases({{m.w,false},{m.x,false},{m.y,true},
                             {m.workspace,true},{observation,true}});
 const std::array ids{m.w,m.x,m.y,observation};DualStore operation;
 auto event=d.compute(operation,ids,{});return {event,event,1};
}
} // namespace head_observation
