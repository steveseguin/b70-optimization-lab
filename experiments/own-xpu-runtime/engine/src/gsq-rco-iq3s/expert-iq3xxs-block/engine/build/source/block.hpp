#pragma once
// Candidate only. Frozen generic control remains unchanged.
#include "gsq-rco-iq3s/integration/build/private/additive/packed.hpp"
#include "gsq-rco-iq3s/expert-iq3xxs-block/selection.hpp"
#include "stage2/packet194-expert-diet-engine/decode_next2.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/dn2_kernels.hpp"
#include "stage2/packet194-expert-diet-engine/expert_groups.hpp"
#endif
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
#ifndef OWN_RT_HOST_ONLY
// Several rows per subgroup (F32 activations): one subgroup owns R consecutive rows of one slot and shares each
// activation element across them. Every row keeps block_lane_sum's exact sequence (block, group, lane), the same
// block_element value (its sign/scale word read as two 16-bit halves of the same bytes), product then add, and the
// adjacent-pair tree; inactive rows still write NaN. Microbench (10 x 640 x 2560): 98.3 -> 60.6 us with R=4.
inline float block_element_words(const uint8_t*b,float d,unsigned group,unsigned lane){
 const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16,code=(word>>(7*(lane/8)))&127;
 const auto mask=code|((std::popcount(code)%2)<<7);
 const int sign=(mask>>(lane%8))&1?-1:1;
 // The grid index byte b[2+group*8+lane/4], read from the group's 16-bit index words (same byte; microbench 60.7 -> 57.1 us).
 const uint32_t index=(uint32_t(reinterpret_cast<const uint16_t*>(b+2+group*8)[lane/8])>>(8*((lane/4)%2)))&255;
 const auto mag=(iq3::iq3_grid[index]>>(8*(lane%4)))&255;
 return (((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
}
template<unsigned R> class BlockRowsKernel;
template<unsigned R> struct BlockRowsOperation final:ownrt::SyclOperation {
 Shape s{};
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  Bound b{s,static_cast<const uint8_t*>(p[0]),static_cast<const uint16_t*>(p[1]),static_cast<uint16_t*>(p[2]),static_cast<const iq3::Route*>(p[3]),static_cast<uint32_t*>(p[4])};
  const size_t blocks=(b.s.rows+R-1)/R;
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<BlockRowsKernel<R>>(sycl::nd_range<1>(blocks*b.s.count*32,32),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
   const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*R;
   const auto r=b.routes[slot];const bool valid=iq3::valid_route(r,b.s.experts,uint32_t(b.s.rows),uint32_t(b.s.rows));
   const float* x=reinterpret_cast<const float*>(b.x)+size_t(slot)*b.s.columns;float acc[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i)acc[i]=0;
   // Lean loop, same sequence: row pointers hoisted, 32-bit block/column index, unrolled groups.
   const uint8_t* rows[R];bool live[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i){const size_t row=first+i;live[i]=valid&&row<b.s.rows&&row<r.row_count;rows[i]=live[i]?b.w+(size_t(r.expert_id)*b.s.rows+r.row_begin+row)*b.s.row_bytes:b.w;}
   const uint32_t nblocks=uint32_t(b.s.columns/256);
   for(uint32_t block=0;block<nblocks;++block){
    #pragma unroll
    for(unsigned i=0;i<R;++i){if(!live[i])continue;
     const auto*packed=rows[i]+block*98u;const float d=iq3::half(iq3::u16(packed));
     #pragma unroll
     for(unsigned group=0;group<8;++group){const uint32_t k=block*256u+group*32u+lane;const float weight=block_element_words(packed,d,group,lane);const float product=weight*x[k];acc[i]=acc[i]+product;}}
   }
   #pragma unroll
   for(unsigned i=0;i<R;++i){float sum=acc[i];
    for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    const size_t row=first+i;
    if(lane==0&&row<b.s.rows)reinterpret_cast<float*>(b.y)[size_t(slot)*b.s.rows+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&first==0&&b.status)b.status[slot]=!valid;
  }));});
 }
};
// OWNRT_DECODE_NEXT2 xxs (lab 2026-10-26): BlockRowsOperation<4>'s rows with packed logical lanes (dn2::xxs_packed:
// one grid word, sign code and scale factor per four lanes, grid in work-group memory; each lane's values, products,
// add order and the tree unchanged), four rows per 32-lane subgroup, four subgroups per work-group.
// Rank-1 profile, 18 sites: 1074 -> 730 us; end to end -0.34 ms per half (16-lane subgroups: 1074 -> ~945 us).
class XxsDn2Kernel;
struct XxsDn2Operation final:ownrt::SyclOperation {
 Shape s{};
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const dn2::XxsView v{static_cast<const uint8_t*>(p[0]),reinterpret_cast<const float*>(p[1]),reinterpret_cast<float*>(p[2]),static_cast<const iq3::Route*>(p[3]),static_cast<uint32_t*>(p[4]),
   uint32_t(s.rows),uint32_t(s.columns),uint32_t(s.row_bytes),uint32_t(s.count),uint32_t(s.experts)};
  constexpr unsigned WGSG=4;const uint32_t total=((v.rows+3)/4)*v.count,groups=(total+WGSG-1)/WGSG;
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<XxsDn2Kernel>(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{dn2::xxs_packed<WGSG>(v,it);}));});
 }
};
inline bool block_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_IQ3_BLOCK_ROWS");return !e||e[0]!='0';}();return on;}
// OWNRT_EXPERTS_GROUPED=1 (2026-10-30, research/multirow-verify-2026-10-30; default off): a chunk's 11..64 slots run as
// groups of up to 4 slots sharing an expert (xgroup2::xxs_grouped: xxs_packed's values, order and tree per member).
class XxsGroupedKernel;
struct XxsGroupedOperation final:ownrt::SyclOperation {
 Shape s{};
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const dn2::XxsView v{static_cast<const uint8_t*>(p[0]),reinterpret_cast<const float*>(p[1]),reinterpret_cast<float*>(p[2]),static_cast<const iq3::Route*>(p[3]),static_cast<uint32_t*>(p[4]),
   uint32_t(s.rows),uint32_t(s.columns),uint32_t(s.row_bytes),uint32_t(s.count),uint32_t(s.experts)};
  // One subgroup per (four-row block, possible group): G = the slot count, the worst case.
  constexpr unsigned WGSG=4;const uint32_t G=v.count,total=((v.rows+3)/4)*G,groups=(total+WGSG-1)/WGSG;
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<XxsGroupedKernel>(sycl::nd_range<1>(size_t(groups)*32*WGSG,32*WGSG),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{xgroup2::xxs_grouped<WGSG,4>(v,G,it);}));});
 }
};
#endif
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
// compact (2026-10-28, OWNRT_TP_EXPERTS=compact): a TP card's own slots only (fewer than one token's ten); each slot's
// rows keep the kernel, decode and reduction order.
inline integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,std::string_view label,std::string_view weight,gsqn::InputMode input,bool compact=false){
 require(selected(label,weight),"IQ3 block exact gate/up site identity");
 require(unsigned(m.type)==18&&m.rows==640&&m.columns==2560&&(compact?m.count>=1&&m.count<10:m.count%10==0&&m.count>=10)&&m.count<=10*gsqn::max_tokens&&m.tokens==1&&m.experts==512&&m.span==640&&m.routes&&m.status,"IQ3 block exact routed geometry");
 require(input==gsqn::InputMode::per_slot,"IQ3 block requires original gathered per-slot input");
 const auto shape=gsqn::validate(d,m,input,gsqn::Storage::packed_direct);
 std::array<ownrt::Allocation,5>ids{m.w,m.x,m.y,m.routes,m.status};
#ifndef OWN_RT_HOST_ONLY
 if(shape.f32&&!shape.row_major&&!compact&&xgroup2::applies(uint32_t(m.count))&&shape.columns%256==0){XxsGroupedOperation op;op.s=shape;auto e=d.compute(op,ids,{});return {e,e,1};}
 if(shape.f32&&!shape.row_major&&block_rows()&&decode_next2::enabled("xxs")&&shape.columns%256==0){XxsDn2Operation op;op.s=shape;auto e=d.compute(op,ids,{});return {e,e,1};}
 if(shape.f32&&!shape.row_major&&block_rows()){BlockRowsOperation<4> op;op.s=shape;auto e=d.compute(op,ids,{});return {e,e,1};}
#endif
 if(shape.f32){BlockOperation<true> op;op.s=shape;auto e=d.compute(op,ids,{});return {e,e,1};}
 BlockOperation<> op;op.s=shape;auto e=d.compute(op,ids,{});return {e,e,1};
}
} // namespace iq3block
