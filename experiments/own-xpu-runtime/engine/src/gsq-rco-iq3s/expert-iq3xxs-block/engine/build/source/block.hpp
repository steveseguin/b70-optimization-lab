#pragma once
// Candidate only. Frozen generic control remains unchanged.
#include "gsq-rco-iq3s/integration/build/private/additive/packed.hpp"
#include "gsq-rco-iq3s/expert-iq3xxs-block/selection.hpp"
namespace iq3block {
using gsqn::Shape;using gsqn::Bound;
// Identical scalar decoder multiplication order; only block half conversion
// and address/group expressions are hoisted. No expanded representation.
inline float block_element(const uint8_t*b,float d,unsigned group,unsigned lane){
 const auto word=iq3::u32(b+66+4*group),code=(word>>(7*(lane/8)))&127;
 const auto mask=code|((std::popcount(code)%2)<<7);
 const int sign=(mask>>(lane%8))&1?-1:1;
 const auto mag=(iq3::iq3_grid[b[2+group*8+lane/4]]>>(8*(lane%4)))&255;
 return (((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
}
template<bool F=false> inline float block_lane_sum(const Bound&b,const iq3::Route&r,size_t row,unsigned slot,unsigned lane){
 const auto*w=b.w+(size_t(r.expert_id)*b.s.rows+r.row_begin+row)*b.s.row_bytes;
 const size_t xb=size_t(slot)*b.s.columns;float sum=0;
 for(size_t block=0;block<b.s.columns/256;++block){
  const auto*packed=w+block*98;const float d=iq3::half(iq3::u16(packed));
  for(unsigned group=0;group<8;++group){
   const size_t k=block*256+group*32+lane;
   const float weight=block_element(packed,d,group,lane);
   const float product=weight*gsqn::act_in<F>(b.x,xb+k);sum=sum+product;
  }
 }
 return sum;
}
using gsqn::require;
template<bool F> class BlockKernel;
template<bool F=false> struct BlockOperation final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 Shape s{};
 Bound bind(std::span<void*const>p)const{return {s,static_cast<const uint8_t*>(p[0]),static_cast<const uint16_t*>(p[1]),static_cast<uint16_t*>(p[2]),s.routed?static_cast<const iq3::Route*>(p[3]):nullptr,s.routed?static_cast<uint32_t*>(p[4]):nullptr};}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{
  auto b=bind(p);
  for(unsigned slot=0;slot<s.count;++slot){auto r=b.routes?b.routes[slot]:iq3::Route{0,0,uint32_t(s.rows)};const bool valid=iq3::valid_route(r,s.experts,uint32_t(s.rows),uint32_t(s.rows));
   if(b.status)b.status[slot]=!valid;
   for(size_t row=0;row<s.rows;++row){float sums[32]{};const bool active=valid&&row<r.row_count;if(active)for(unsigned lane=0;lane<32;++lane)sums[lane]=block_lane_sum<F>(b,r,row,slot,lane);gsqn::act_out<F>(b.y,size_t(slot)*s.rows+row,active?iq3::tree32(sums):iq3::bits_float(0x7fc00000));}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const auto b=bind(p);
  // Outer command owns by-value pointers/shape/dependencies. No caller span or
  // operation object survives by reference in the prepared callback.
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<BlockKernel<F>>(sycl::nd_range<1>(b.s.rows*b.s.count*32,32),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();const auto rs=gsqn::row_slot(b.s,logical);const size_t row=rs.first;const unsigned slot=rs.second;
   const auto r=b.routes?b.routes[slot]:iq3::Route{0,0,uint32_t(b.s.rows)};const bool valid=iq3::valid_route(r,b.s.experts,uint32_t(b.s.rows),uint32_t(b.s.rows)),active=valid&&row<r.row_count;
   float sum=active?block_lane_sum<F>(b,r,row,slot,lane):0.f;
   for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
   if(lane==0){gsqn::act_out<F>(b.y,size_t(slot)*b.s.rows+row,active?sum:iq3::bits_float(0x7fc00000));if(row==0&&b.status)b.status[slot]=!valid;}
  }));});
 }
#endif
};
inline integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,std::string_view label,std::string_view weight,gsqn::InputMode input){
 require(selected(label,weight),"IQ3 block exact gate/up site identity");
 require(unsigned(m.type)==18&&m.rows==640&&m.columns==2560&&m.count%10==0&&m.count>=10&&m.count<=10*gsqn::max_tokens&&m.tokens==1&&m.experts==512&&m.span==640&&m.routes&&m.status,"IQ3 block exact routed geometry");
 require(input==gsqn::InputMode::per_slot,"IQ3 block requires original gathered per-slot input");
 const auto shape=gsqn::validate(d,m,input,gsqn::Storage::packed_direct);
 std::array<ownrt::Allocation,5>ids{m.w,m.x,m.y,m.routes,m.status};
 if(shape.f32){BlockOperation<true> op;op.s=shape;auto e=d.compute(op,ids,{});return {e,e,1};}
 BlockOperation<> op;op.s=shape;auto e=d.compute(op,ids,{});return {e,e,1};
}
} // namespace iq3block
