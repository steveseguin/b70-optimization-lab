#pragma once
#include "gsq-rco-iq3s/integration/build/private/additive/packed.hpp"
#include "gsq-rco-iq3s/dense-packed-block/selection.hpp"
#include "stage2/packet194-expert-diet-engine/prefill_switches.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prefill_reuse2_op.hpp"
#endif
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
template<unsigned T,bool F=false> inline float block_lane_sum(const gsqn::Bound&b,const iq3::Route&r,size_t row,unsigned slot,unsigned lane){
 constexpr size_t bytes=T==12?144:T==13?176:136;
 const auto*w=b.w+(size_t(r.expert_id)*b.s.rows+r.row_begin+row)*b.s.row_bytes;
 const size_t xb=b.s.per_slot?size_t(slot)*b.s.columns:0;float sum=0;
 for(size_t block=0;block<b.s.columns/256;++block){
  const auto*packed=w+block*bytes;
  const float d=iq3::half(iq3::u16(packed));
  float dmin=0;if constexpr(T==12||T==13)dmin=iq3::half(iq3::u16(packed+2));
  for(unsigned group=0;group<8;++group){
   const size_t k=block*256+group*32+lane;
   const float weight=block_element<T>(packed,d,dmin,group,lane);
   const float product=weight*gsqn::act_in<F>(b.x,xb+k);sum=sum+product;
  }
 }
 return sum;
}
}

namespace denseblock {
using gsqn::Shape;using gsqn::Bound;using gsqn::require;
template<unsigned T,bool F> class DenseBlockKernel;
template<unsigned T,bool F=false> struct DenseBlockOperation final:
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
   for(size_t row=0;row<s.rows;++row){float sums[32]{};const bool active=valid&&row<r.row_count;if(active)for(unsigned lane=0;lane<32;++lane)sums[lane]=block_lane_sum<T,F>(b,r,row,slot,lane);gsqn::act_out<F>(b.y,size_t(slot)*s.rows+row,active?iq3::tree32(sums):iq3::bits_float(0x7fc00000));}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const auto b=bind(p);
  if constexpr(F)if(gsqn::v2::enabled()&&!b.routes&&!b.s.routed&&b.s.count==1&&b.s.experts==1&&!b.s.per_slot&&!b.s.row_major&&gsqn::v2::fits<T>(b.w,b.s.rows,b.s.columns,b.s.row_bytes)){
   // OWNRT_DENSE_DECODE_V2=1: same values, fewer memory messages, uniform per-block arithmetic (dense_decode_v2.hpp).
   const uint32_t rows=uint32_t(b.s.rows),cols=uint32_t(b.s.columns),rb=uint32_t(b.s.row_bytes);const uint8_t* w=b.w;
   const float* x=reinterpret_cast<const float*>(b.x);float* y=reinterpret_cast<float*>(b.y);
   const unsigned R=gsqn::v2::rows_per_subgroup(rows);const size_t global=((rows+R-1)/R*32+127)/128*128;
   if(R==4)return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(global,128),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{gsqn::v2::rows_fast<T,4>(w,x,y,rows,cols,rb,it);}));});
   return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(global,128),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{gsqn::v2::rows_fast<T,1>(w,x,y,rows,cols,rb,it);}));});
  }
  // Outer command owns by-value pointers/shape/dependencies. No caller span or
  // operation object survives by reference in the prepared callback.
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<DenseBlockKernel<T,F>>(sycl::nd_range<1>(b.s.rows*b.s.count*32,32),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();const auto rs=gsqn::row_slot(b.s,logical);const size_t row=rs.first;const unsigned slot=rs.second;
   const auto r=b.routes?b.routes[slot]:iq3::Route{0,0,uint32_t(b.s.rows)};const bool valid=iq3::valid_route(r,b.s.experts,uint32_t(b.s.rows),uint32_t(b.s.rows)),active=valid&&row<r.row_count;
   float sum=active?block_lane_sum<T,F>(b,r,row,slot,lane):0.f;
   for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
   if(lane==0){gsqn::act_out<F>(b.y,size_t(slot)*b.s.rows+row,active?sum:iq3::bits_float(0x7fc00000));if(row==0&&b.status)b.status[slot]=!valid;}
  }));});
 }
#endif
};

#ifndef OWN_RT_HOST_ONLY
// Dense token rows with weight reuse (F32 activations): one subgroup owns one weight row and a tile of R token rows.
// Each block_element value is decoded once and applied to every token of the tile; each token keeps block_lane_sum's
// exact (block, group, lane) sequence, product then add, and the adjacent-pair subgroup tree.
template<unsigned T,unsigned R> class DenseBlockRowsKernel;
template<unsigned T,unsigned R> struct DenseBlockRows final:ownrt::SyclOperation {
 Shape s{};
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const auto sh=s;const auto*W=static_cast<const uint8_t*>(p[0]);const auto*X=static_cast<const float*>(p[1]);auto*Y=static_cast<float*>(p[2]);
  const size_t tiles=(sh.count+R-1)/R;
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<DenseBlockRowsKernel<T,R>>(sycl::nd_range<1>(sh.rows*tiles*32,32),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   constexpr size_t bytes=T==12?144:T==13?176:136;
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
   const size_t row=logical/tiles,first=(logical%tiles)*R;const unsigned n=unsigned(std::min<size_t>(R,sh.count-first));
   const auto*w=W+row*sh.row_bytes;float sums[R];for(unsigned r=0;r<R;++r)sums[r]=0;
   for(size_t block=0;block<sh.columns/256;++block){
    const auto*packed=w+block*bytes;const float d=iq3::half(iq3::u16(packed));
    float dmin=0;if constexpr(T==12||T==13)dmin=iq3::half(iq3::u16(packed+2));
    for(unsigned group=0;group<8;++group){
     const size_t k=block*256+group*32+lane;const float weight=block_element<T>(packed,d,dmin,group,lane);
     for(unsigned r=0;r<R;++r)if(r<n){const float product=weight*X[(first+r)*sh.columns+k];sums[r]=sums[r]+product;}
    }
   }
   for(unsigned r=0;r<R;++r){float sum=sums[r];
    for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    if(lane==0&&r<n)Y[(first+r)*sh.rows+row]=sum;}
  }));});
 }
};
// Generation-2 token rows (OWNRT_PREFILL_REUSE2=1, prefill_reuse2.hpp): RW rows x T tokens per subgroup, each
// block_element value decoded once per tile; every output keeps block_lane_sum's sequence and the subgroup tree.
struct BlockElement {template<unsigned T> static float element(const uint8_t*b,float d,float dmin,unsigned group,unsigned lane){return block_element<T>(b,d,dmin,group,lane);}};
#endif
// tp_rows (2026-10-28): a TP card's whole rows of the site (head split), each row's arithmetic unchanged; 0 = all rows.
inline const Site& policy(const integrated::Matrix&m,std::string_view label,std::string_view weight,gsqn::InputMode input,size_t tp_rows=0){
 const auto*s=selected(label,weight);require(s,"dense block exact census site");
 require(tp_rows<s->rows&&unsigned(m.type)==s->type&&m.rows==(tp_rows?tp_rows:s->rows)&&m.columns==2560&&m.span==m.rows,"dense block exact geometry/type/span");
 require(m.count==1&&m.experts==1&&!m.routes&&!m.status&&(m.tokens==1?input==gsqn::InputMode::shared:input==gsqn::InputMode::per_slot),"dense block dense input: shared, or per-slot token rows");
 require(!m.fp32&&((m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16)||(m.activation==iq3::Type::F32&&m.output_type==iq3::Type::F32)),"dense block activation/output both BF16 or both F32");
 require(gsq::row_bytes(s->type,m.columns)*s->rows==s->bytes,"dense block exact packed extent");return *s;
}
template<unsigned T> inline integrated::Launch issue(ownrt::Device&d,const integrated::Matrix&m,Shape s){std::array<ownrt::Allocation,5>ids{m.w,m.x,m.y,m.x,m.y};
#ifndef OWN_RT_HOST_ONLY
 if(s.f32&&s.row_major&&reuse2::enabled()&&s.columns%256==0&&reuse2::aligned(d,m.x,16)){
  // OWNRT_PREFILL_REUSE2_SMALL=1: 2..4 token rows use a small-row tile (prefill_reuse2_op.hpp small_config).
  // Its dense-block format is reuse2::BlockV2 (the one-row decode kernel's header loads) when rows_fast's alignment holds.
  if(const unsigned sc=reuse2::small_config("BLOCK",uint32_t(s.count),reuse2::default_small("BLOCK",uint32_t(s.rows),uint32_t(s.columns)));sc!=reuse2::no_small){
   std::array<ownrt::Allocation,3> rows{m.w,m.x,m.y};ownrt::Event e{};
   if(gsqn::v2::fits<T>(static_cast<const uint8_t*>(d.arena.row(m.w).pointer),s.rows,s.columns,s.row_bytes))
    e=reuse2::issue<reuse2::BlockV2<T>,REUSE2_SMALL_CONFIGS>(d,sc,rows,uint32_t(s.rows),uint32_t(s.columns),s.count,uint32_t(s.row_bytes));
   else e=reuse2::issue<reuse2::Block32<T,BlockElement>,REUSE2_SMALL_CONFIGS>(d,sc,rows,uint32_t(s.rows),uint32_t(s.columns),s.count,uint32_t(s.row_bytes));
   return {e,e,1};
  }
  // OWNRT_PREFILL_REUSE2_BLOCK=i selects the tile (default reuse2::default_block); the x rows are 16-byte aligned for subgroup block reads.
  if(const unsigned c=reuse2::config("BLOCK",reuse2::config_count,reuse2::default_block(uint32_t(s.rows),uint32_t(s.columns)));c<reuse2::config_count){
   std::array<ownrt::Allocation,3> rows{m.w,m.x,m.y};
   auto e=reuse2::issue<reuse2::Block32<T,BlockElement>,REUSE2_CONFIGS>(d,c,rows,uint32_t(s.rows),uint32_t(s.columns),s.count,uint32_t(s.row_bytes));
   return {e,e,1};
  }
 }
 if(s.f32&&s.row_major&&prefill_switches::small_tile_rows()){DenseBlockRows<T,4>op;op.s=s;std::array<ownrt::Allocation,3>rows{m.w,m.x,m.y};auto e=d.compute(op,rows,{});return {e,e,1};}
#endif
 if(s.f32){DenseBlockOperation<T,true>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
 DenseBlockOperation<T>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
inline integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,std::string_view label,std::string_view weight,gsqn::InputMode input,size_t tp_rows=0){
 policy(m,label,weight,input,tp_rows);auto s=gsqn::validate(d,m,input,gsqn::Storage::packed_direct);
 switch(unsigned(m.type)){case 12:return denseblock::issue<12>(d,m,s);case 13:return denseblock::issue<13>(d,m,s);case 23:return denseblock::issue<23>(d,m,s);}throw std::invalid_argument("dense block unsupported type");
}
} // namespace denseblock
