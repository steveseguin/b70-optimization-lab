#pragma once
#include "../native-formats/packed.hpp"
#include "selection.hpp"
// Included after frozen gsqn definitions. Candidate changes only repeated
// block half conversion/addressing, never the scalar FP expression boundaries.
namespace denseblock {
template<unsigned T> inline float block_element(const uint8_t*b,float d,float dmin,unsigned group,unsigned lane){
 static_assert(T==12||T==13||T==23);
 if constexpr(T==12||T==13){
  const auto*s=b+4;
  const unsigned scale=group<4?s[group]&63:(s[group+4]&15)|((s[group-4]>>6)<<4);
  const unsigned minimum=group<4?s[group+4]&63:(s[group+4]>>4)|((s[group]>>6)<<4);
  constexpr unsigned low_offset=T==12?16:48;
  unsigned code=(b[low_offset+(group/2)*32+lane]>>(4*(group%2)))&15;
  if constexpr(T==13)code|=((b[16+lane]>>group)&1)<<4;
  const float factor=d*float(scale);
  const float offset=dmin*float(minimum);
  const float product=factor*float(code);return product-offset;
 }else{
  constexpr int levels[]{-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
  const unsigned scale=((b[4+group/2]>>(4*(group%2)))&15)|(((iq3::u16(b+2)>>(2*group))&3)<<4);
  const unsigned code=(b[8+group*16+lane%16]>>(4*(lane/16)))&15;
  const float factor=d*float(int(scale)-32);
  return factor*float(levels[code]);
 }
}
template<unsigned T> inline float block_lane_sum(const gsqn::Bound&b,const iq3::Route&r,size_t row,unsigned slot,unsigned lane){
 constexpr size_t bytes=T==12?144:T==13?176:136;
 const auto*w=b.w+(size_t(r.expert_id)*b.s.rows+r.row_begin+row)*b.s.row_bytes;
 const auto*x=b.x+(b.s.per_slot?size_t(slot)*b.s.columns:0);float sum=0;
 for(size_t block=0;block<b.s.columns/256;++block){
  const auto*packed=w+block*bytes;
  const float d=iq3::half(iq3::u16(packed));
  float dmin=0;if constexpr(T==12||T==13)dmin=iq3::half(iq3::u16(packed+2));
  for(unsigned group=0;group<8;++group){
   const size_t k=block*256+group*32+lane;
   const float weight=block_element<T>(packed,d,dmin,group,lane);
   const float product=weight*iq3::bits_float(uint32_t(x[k])<<16);sum=sum+product;
  }
 }
 return sum;
}
}

namespace denseblock {
using gsqn::Shape;using gsqn::Bound;using gsqn::require;
template<unsigned T> class DenseBlockKernel;
template<unsigned T> struct DenseBlockOperation final:
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
   for(size_t row=0;row<s.rows;++row){float sums[32]{};const bool active=valid&&row<r.row_count;if(active)for(unsigned lane=0;lane<32;++lane)sums[lane]=block_lane_sum<T>(b,r,row,slot,lane);b.y[size_t(slot)*s.rows+row]=iq3::bf16_bits(active?iq3::tree32(sums):iq3::bits_float(0x7fc00000));}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const auto b=bind(p);
  // Outer command owns by-value pointers/shape/dependencies. No caller span or
  // operation object survives by reference in the prepared callback.
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<DenseBlockKernel<T>>(sycl::nd_range<1>(b.s.rows*b.s.count*32,32),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id(),row=logical%b.s.rows;const unsigned slot=logical/b.s.rows;
   const auto r=b.routes?b.routes[slot]:iq3::Route{0,0,uint32_t(b.s.rows)};const bool valid=iq3::valid_route(r,b.s.experts,uint32_t(b.s.rows),uint32_t(b.s.rows)),active=valid&&row<r.row_count;
   float sum=active?block_lane_sum<T>(b,r,row,slot,lane):0.f;
   for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
   if(lane==0){b.y[logical]=iq3::bf16_bits(active?sum:iq3::bits_float(0x7fc00000));if(row==0&&b.status)b.status[slot]=!valid;}
  }));});
 }
#endif
};

inline const Site& policy(const integrated::Matrix&m,std::string_view label,std::string_view weight,gsqn::InputMode input){
 const auto*s=selected(label,weight);require(s,"dense block exact census site");
 require(unsigned(m.type)==s->type&&m.rows==s->rows&&m.columns==2560&&m.span==m.rows,"dense block exact geometry/type/span");
 require(m.count==1&&m.experts==1&&!m.routes&&!m.status&&input==gsqn::InputMode::shared,"dense block original dense shared input");
 require(m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16&&!m.fp32,"dense block original BF16 precision");
 require(gsq::row_bytes(s->type,m.columns)*m.rows==s->bytes,"dense block exact packed extent");return *s;
}
template<unsigned T> inline integrated::Launch issue(ownrt::Device&d,const integrated::Matrix&m,Shape s){DenseBlockOperation<T>op;op.s=s;std::array<ownrt::Allocation,5>ids{m.w,m.x,m.y,m.x,m.y};auto e=d.compute(op,ids,{});return {e,e,1};}
inline integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,std::string_view label,std::string_view weight,gsqn::InputMode input){
 policy(m,label,weight,input);auto s=gsqn::validate(d,m,input,gsqn::Storage::packed_direct);
 switch(unsigned(m.type)){case 12:return denseblock::issue<12>(d,m,s);case 13:return denseblock::issue<13>(d,m,s);case 23:return denseblock::issue<23>(d,m,s);}throw std::invalid_argument("dense block unsupported type");
}
} // namespace denseblock
