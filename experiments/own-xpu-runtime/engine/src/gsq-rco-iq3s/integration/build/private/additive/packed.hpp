#pragma once
// An additive Engine overlay may supply its own internally consistent checked
// runtime header closure before including this facade.
#ifndef GSQN_RUNTIME_HEADERS_PROVIDED
#error "Engine runtime closure required"
#endif
#include "device_formats.hpp"
#include "stage2/packet194-expert-diet-engine/experts_v2.hpp"
#include "dense_decode_v2.hpp"
#include <array>
#include <utility>
namespace gsqn {
enum class InputMode {shared,per_slot};
enum class Storage {packed_direct};
inline void require(bool b,const char*s){if(!b)throw std::invalid_argument(s);}
inline size_t multiply(size_t a,size_t b){require(!b||a<=SIZE_MAX/b,"GSQ extent overflow");return a*b;}
// row_major: dense token rows (count = tokens, per-slot input), work-groups ordered so tokens sharing a weight row
// run together. Output index is always slot*rows+row, so the original slot-major mapping is unchanged.
struct Shape {size_t rows,columns,row_bytes;uint32_t count,experts;bool routed,per_slot,f32=false,row_major=false;};
// Inverse of the work-group order: {row, slot}.
inline std::pair<size_t,unsigned> row_slot(const Shape& s,size_t logical){if(s.row_major)return {logical/s.count,unsigned(logical%s.count)};return {logical%s.rows,unsigned(logical/s.rows)};}
// Activation storage helpers shared by every packed GEMV family. F=false: BF16 (tuned default); F=true: F32
// exact mode. Pointers keep their BF16 declared type; F32 reinterprets and indexes in float elements.
template<bool F> inline float act_in(const uint16_t*x,size_t i){if constexpr(F)return reinterpret_cast<const float*>(x)[i];else return iq3::bits_float(uint32_t(x[i])<<16);}
template<bool F> inline void act_out(uint16_t*y,size_t i,float v){if constexpr(F)reinterpret_cast<float*>(y)[i]=v;else y[i]=iq3::bf16_bits(v);}
// Upper bound on token rows per launch (batched prefill chunk); routed sites carry 10 slots per token.
inline constexpr uint32_t max_tokens=256;
struct Bound {Shape s;const uint8_t*w;const uint16_t*x;uint16_t*y;const iq3::Route*routes;uint32_t*status;};
template<unsigned T,bool F=false> inline float lane_sum(const Bound&b,const iq3::Route&r,size_t row,unsigned slot,unsigned lane){
 constexpr size_t elements=T==42?64:256;constexpr size_t bytes=T==42?18:T==12?144:T==13?176:T==23?136:98;
 const auto*w=b.w+(size_t(r.expert_id)*b.s.rows+r.row_begin+row)*b.s.row_bytes;
 const size_t xb=b.s.per_slot?size_t(slot)*b.s.columns:0;float sum=0;
 for(size_t k=lane;k<b.s.columns;k+=32){const float weight=gsq::element_unchecked(T,w+(k/elements)*bytes,k%elements);const float product=weight*act_in<F>(b.x,xb+k);sum=sum+product;}
 return sum;
}
template<unsigned T,bool F> class PackedKernel;
template<unsigned T,bool F=false> struct PackedOperation final:
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
   for(size_t row=0;row<s.rows;++row){float sums[32]{};const bool active=valid&&row<r.row_count;if(active)for(unsigned lane=0;lane<32;++lane)sums[lane]=lane_sum<T,F>(b,r,row,slot,lane);act_out<F>(b.y,size_t(slot)*s.rows+row,active?iq3::tree32(sums):iq3::bits_float(0x7fc00000));}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const auto b=bind(p);
  if constexpr(F&&(T==12||T==13||T==23))if(v2::enabled()&&!b.routes&&!b.s.routed&&b.s.count==1&&b.s.experts==1&&!b.s.per_slot&&!b.s.row_major&&v2::fits<T>(b.w,b.s.rows,b.s.columns,b.s.row_bytes)){
   // OWNRT_DENSE_DECODE_V2=1: dense decode rows, lane_sum's values and order (dense_decode_v2.hpp).
   const uint32_t rows=uint32_t(b.s.rows),cols=uint32_t(b.s.columns),rb=uint32_t(b.s.row_bytes);const uint8_t* w=b.w;
   const float* x=reinterpret_cast<const float*>(b.x);float* y=reinterpret_cast<float*>(b.y);
   const unsigned R=v2::rows_per_subgroup(rows);const size_t global=((rows+R-1)/R*32+127)/128*128;
   if(R==4)return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(global,128),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{v2::rows_fast<T,4>(w,x,y,rows,cols,rb,it);}));});
   return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(global,128),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{v2::rows_fast<T,1>(w,x,y,rows,cols,rb,it);}));});
  }
  // Outer command owns by-value pointers/shape/dependencies. No caller span or
  // operation object survives by reference in the prepared callback.
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<PackedKernel<T,F>>(sycl::nd_range<1>(b.s.rows*b.s.count*32,32),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();const auto rs=row_slot(b.s,logical);const size_t row=rs.first;const unsigned slot=rs.second;
   const auto r=b.routes?b.routes[slot]:iq3::Route{0,0,uint32_t(b.s.rows)};const bool valid=iq3::valid_route(r,b.s.experts,uint32_t(b.s.rows),uint32_t(b.s.rows)),active=valid&&row<r.row_count;
   float sum=active?lane_sum<T,F>(b,r,row,slot,lane):0.f;
   for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
   if(lane==0){act_out<F>(b.y,size_t(slot)*b.s.rows+row,active?sum:iq3::bits_float(0x7fc00000));if(row==0&&b.status)b.status[slot]=!valid;}
  }));});
 }
#endif
};
#ifndef OWN_RT_HOST_ONLY
// Routed rows, several per subgroup (F32 activations): one subgroup owns R consecutive rows of one slot and shares each
// activation element across them. Every row keeps lane_sum's exact sequence (k = lane + 32*i), the same element value,
// product then add, and the adjacent-pair tree; inactive rows still write NaN. Microbench (Q2_0 down 10 x 2560 x 640):
// 151.7 -> 73.9 us with R=4.
template<unsigned T,unsigned R> class PackedRowsKernel;
template<unsigned T,unsigned R> struct PackedRowsOperation final:ownrt::SyclOperation {
 Shape s{};
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const Bound b{s,static_cast<const uint8_t*>(p[0]),static_cast<const uint16_t*>(p[1]),static_cast<uint16_t*>(p[2]),static_cast<const iq3::Route*>(p[3]),static_cast<uint32_t*>(p[4])};
  const size_t blocks=(b.s.rows+R-1)/R;
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<PackedRowsKernel<T,R>>(sycl::nd_range<1>(blocks*b.s.count*32,32),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   constexpr size_t elements=T==42?64:256;constexpr size_t bytes=T==42?18:T==12?144:T==13?176:T==23?136:98;
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id();
   const unsigned slot=unsigned(logical/blocks);const size_t first=(logical%blocks)*R;
   const auto r=b.routes[slot];const bool valid=iq3::valid_route(r,b.s.experts,uint32_t(b.s.rows),uint32_t(b.s.rows));
   const float* x=reinterpret_cast<const float*>(b.x)+(b.s.per_slot?size_t(slot)*b.s.columns:0);float acc[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i)acc[i]=0;
   // Lean loop, same sequence: row pointers hoisted, 32-bit column index.
   const uint8_t* rows[R];bool live[R];
   #pragma unroll
   for(unsigned i=0;i<R;++i){const size_t row=first+i;live[i]=valid&&row<b.s.rows&&row<r.row_count;rows[i]=live[i]?b.w+(size_t(r.expert_id)*b.s.rows+r.row_begin+row)*b.s.row_bytes:b.w;}
   const uint32_t columns=uint32_t(b.s.columns);
   if constexpr(T==42) {
    // Q2_0: the block's half scale is read once per row and block (element_unchecked reads the same value for each
    // element); k still runs lane, lane+32, ... and each weight is float(code-1)*d as in element_unchecked.
    for(uint32_t block=0;block<columns/64u;++block){
     float d[R];
     #pragma unroll
     for(unsigned i=0;i<R;++i)d[i]=live[i]?iq3::half(iq3::u16(rows[i]+block*18u)):0.f;
     #pragma unroll
     for(unsigned h=0;h<2;++h){const uint32_t e=lane+32u*h,k=block*64u+e;const float input=x[k];
      #pragma unroll
      for(unsigned i=0;i<R;++i){if(!live[i])continue;
       const unsigned code=(rows[i][block*18u+2u+e/4u]>>(2*(e%4u)))&3;const float weight=float(int(code)-1)*d[i];
       const float product=weight*input;acc[i]=acc[i]+product;}}
    }
   } else
   for(uint32_t k=lane;k<columns;k+=32){const float input=x[k];
    #pragma unroll
    for(unsigned i=0;i<R;++i){if(!live[i])continue;
     const float weight=gsq::element_unchecked(T,rows[i]+(k/uint32_t(elements))*uint32_t(bytes),k%uint32_t(elements));const float product=weight*input;acc[i]=acc[i]+product;}}
   #pragma unroll
   for(unsigned i=0;i<R;++i){float sum=acc[i];
    for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    const size_t row=first+i;
    if(lane==0&&row<b.s.rows)reinterpret_cast<float*>(b.y)[size_t(slot)*b.s.rows+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&first==0&&b.status)b.status[slot]=!valid;
  }));});
 }
};
// OWNRT_EXPERTS_V2 (lab 2026-10-26): routed Q2_0 / IQ4_XS rows with packed logical lanes. Work-item m of a row owns the
// LPI adjacent logical lanes m*LPI.. of PackedRowsOperation's mapping (k = lane + 32*i): their quant codes are one load
// and the block (Q2_0) or 32-column group (IQ4_XS) scale is formed once. Each logical lane keeps its exact sequence (the
// same element value as element_unchecked / the Q2_0 branch, k in the same order, product then add); then log2(LPI)
// adjacent-pair tree levels in registers and the rest by shuffles, same operands, same order. Inactive rows write NaN.
template<unsigned T,unsigned SG,unsigned LPI,unsigned RI,unsigned WGSG> class PackedLanesKernel;
template<unsigned T,unsigned SG,unsigned LPI,unsigned RI,unsigned WGSG> struct PackedLanesOperation final:ownrt::SyclOperation {
 static_assert(T==42||T==23,"packed lanes: Q2_0 or IQ4_XS");
 Shape s{};
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const Bound b{s,static_cast<const uint8_t*>(p[0]),static_cast<const uint16_t*>(p[1]),static_cast<uint16_t*>(p[2]),static_cast<const iq3::Route*>(p[3]),static_cast<uint32_t*>(p[4])};
  constexpr unsigned IPR=32/LPI,SETS=SG/IPR,RPS=SETS*RI;
  const uint32_t rows=uint32_t(b.s.rows),columns=uint32_t(b.s.columns),row_bytes=uint32_t(b.s.row_bytes),experts=b.s.experts;
  const uint32_t blocks=(rows+RPS-1)/RPS,total=blocks*b.s.count,groups=(total+WGSG-1)/WGSG;
  const bool per_slot=b.s.per_slot;
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<PackedLanesKernel<T,SG,LPI,RI,WGSG>>(sycl::nd_range<1>(size_t(groups)*SG*WGSG,SG*WGSG),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(SG)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/IPR,m=lane%IPR;
   const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+uint32_t(sg.get_group_linear_id());if(logical>=total)return;
   const uint32_t slot=logical/blocks,first=(logical%blocks)*RPS+set*RI;
   const auto r=b.routes[slot];const bool valid=iq3::valid_route(r,experts,rows,rows);
   const float* x=reinterpret_cast<const float*>(b.x)+(per_slot?size_t(slot)*columns:0);
   float acc[RI][LPI];const uint8_t* rp[RI];bool live[RI];
   #pragma unroll
   for(unsigned i=0;i<RI;++i){
    #pragma unroll
    for(unsigned j=0;j<LPI;++j)acc[i][j]=0;
    const uint32_t row=first+i;live[i]=valid&&row<rows&&row<r.row_count;rp[i]=live[i]?b.w+(size_t(r.expert_id)*rows+r.row_begin+row)*row_bytes:b.w;}
   const unsigned L0=m*LPI;
   if constexpr(T==42){
    for(uint32_t block=0;block<columns/64u;++block){
     float d[RI];
     #pragma unroll
     for(unsigned i=0;i<RI;++i)d[i]=live[i]?iq3::half(iq3::u16(rp[i]+block*18u)):0.f;
     #pragma unroll
     for(unsigned h=0;h<2;++h){
      const uint32_t k0=block*64u+32u*h+L0;float xv[LPI];
      #pragma unroll
      for(unsigned c=0;c<LPI/4;++c){const auto v=*reinterpret_cast<const sycl::vec<float,4>*>(x+k0+4*c);xv[4*c]=v[0];xv[4*c+1]=v[1];xv[4*c+2]=v[2];xv[4*c+3]=v[3];}
      #pragma unroll
      for(unsigned i=0;i<RI;++i){if(!live[i])continue;
       const uint8_t* bp=rp[i]+block*18u+2u+L0/4+8u*h; // e=L0+j+32h: byte 2+e/4, bits 2*(e%4)=2*(j%4)
       const uint32_t codes=LPI==8?uint32_t(*reinterpret_cast<const uint16_t*>(bp)):uint32_t(*bp);
       #pragma unroll
       for(unsigned j=0;j<LPI;++j){const unsigned code=(codes>>(2*j))&3;const float weight=float(int(code)-1)*d[i];
        const float product=weight*xv[j];acc[i][j]=acc[i][j]+product;}}
     }
    }
   } else {
    for(uint32_t n=0;n<columns/32u;++n){
     const uint32_t block=n/8u,group=n%8u,k0=n*32u+L0;float xv[LPI];
     #pragma unroll
     for(unsigned c=0;c<LPI/4;++c){const auto v=*reinterpret_cast<const sycl::vec<float,4>*>(x+k0+4*c);xv[4*c]=v[0];xv[4*c+1]=v[1];xv[4*c+2]=v[2];xv[4*c+3]=v[3];}
     #pragma unroll
     for(unsigned i=0;i<RI;++i){if(!live[i])continue;
      const uint8_t* bp=rp[i]+block*136u;
      const unsigned scale=((bp[4+group/2]>>(4*(group%2)))&15)|(((iq3::u16(bp+2)>>(2*group))&3)<<4);
      const float factor=iq3::half(iq3::u16(bp))*float(int(scale)-32);
      // i=32*group+L: byte 8+16*group+L%16, nibble L/16 (L=L0+j stays inside one 16-lane half).
      const uint32_t* qp=reinterpret_cast<const uint32_t*>(bp+8+16*group+(L0%16));
      uint32_t qw[LPI/4];
      #pragma unroll
      for(unsigned c=0;c<LPI/4;++c)qw[c]=qp[c];
      #pragma unroll
      for(unsigned j=0;j<LPI;++j){const unsigned code=(qw[j/4]>>(8*(j%4)+4*(L0/16)))&15;const float weight=factor*float(iq3::iq4_level(code));
       const float product=weight*xv[j];acc[i][j]=acc[i][j]+product;}}
    }
   }
   #pragma unroll
   for(unsigned i=0;i<RI;++i){
    float t[LPI];
    #pragma unroll
    for(unsigned j=0;j<LPI;++j)t[j]=acc[i][j];
    #pragma unroll
    for(unsigned width=1;width<LPI;width*=2){
     #pragma unroll
     for(unsigned j=0;j<LPI;j+=2*width)t[j]=t[j]+t[j+width];}
    float sum=t[0];
    #pragma unroll
    for(unsigned width=1;width<IPR;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(m%(2*width)==0)sum=sum+rhs;}
    const uint32_t row=first+i;
    if(m==0&&row<rows)reinterpret_cast<float*>(b.y)[size_t(slot)*rows+row]=live[i]?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&(logical%blocks)==0&&b.status)b.status[slot]=!valid;
  }));});
 }
};
inline bool routed_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_GSQ_ROUTED_ROWS");return !e||e[0]!='0';}();return on;}
#endif
inline Shape validate(ownrt::Device&d,const integrated::Matrix&m,InputMode input,Storage storage){
 require(input==InputMode::shared||input==InputMode::per_slot,"GSQ input mode");
 require(storage==Storage::packed_direct,"GSQ packed direct storage only");const auto t=unsigned(m.type);require(t==12||t==13||t==18||t==23||t==42,"GSQ unsupported packed type");
 const bool f32=m.activation==iq3::Type::F32;
 require(!m.fp32&&((m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16)||(f32&&m.output_type==iq3::Type::F32)),"GSQ activation/output must be both BF16 or both F32");
 require(m.rows&&m.rows<=248320&&m.columns&&m.columns<=10240&&m.count&&m.count<=10*max_tokens&&m.experts&&m.experts<=512&&m.tokens&&m.tokens<=max_tokens,"GSQ geometry bound");
 require(!m.span||m.span==m.rows,"GSQ full route span only");
 const bool routed=bool(m.routes);require(routed?bool(m.status)&&m.tokens==1:(m.count==1&&m.experts==1&&!m.status&&(m.tokens==1?input==InputMode::shared:input==InputMode::per_slot)),"GSQ routes/status identity");
 const size_t rb=gsq::row_bytes(t,m.columns);Shape s{m.rows,m.columns,rb,routed?m.count:m.tokens,m.experts,routed,input==InputMode::per_slot,f32,!routed&&m.tokens>1};const size_t ab=f32?4:2;
 std::array<ownrt::Allocation,5> ids{m.w,m.x,m.y,m.routes,m.status};
 const size_t sizes[]{multiply(multiply(m.rows,m.experts),rb),multiply(multiply(m.columns,s.per_slot?s.count:1),ab),multiply(multiply(m.rows,s.count),ab),multiply(m.count,sizeof(iq3::Route)),multiply(m.count,4)};
 const size_t alignment[]{1,ab,ab,alignof(iq3::Route),4};
 for(size_t i=0;i<(routed?5:3);++i){require(ids[i]!=0,"GSQ null binding");const auto&r=d.arena.row(ids[i]);require(r.live&&r.memory==ownrt::Memory::device&&r.bytes>=sizes[i]&&uintptr_t(r.pointer)%alignment[i]==0,"GSQ live extent/alignment");for(size_t j=0;j<i;++j)require(ids[i]!=ids[j],"GSQ distinct operand allocations required");}
 return s;
}
template<unsigned T> inline integrated::Launch issue(ownrt::Device&d,const integrated::Matrix&m,Shape s){std::array<ownrt::Allocation,5>ids{m.w,m.x,m.y,m.routes?m.routes:m.x,m.status?m.status:m.y};
#ifndef OWN_RT_HOST_ONLY
 if constexpr(T==42||T==23) if(s.f32&&s.routed&&!s.row_major&&s.per_slot&&s.count<=experts_v2::max_slots&&experts_v2::enabled(T==42?"q20":"iq4xs")&&reinterpret_cast<uintptr_t>(d.arena.row(m.x).pointer)%16==0&&s.columns%64==0){
  // Q2_0: 8 lanes per item, IQ4_XS: 4 lanes per item, 32-lane subgroups. Microbench cold (10 slots): Q2_0 down
  // 60.1 -> 34.9 us, IQ4_XS gate 98.4 -> 51.8 us; rank-1 profile 114 -> 58 us (2 sites), 211 -> 103 us (2 sites).
  if constexpr(T==42){PackedLanesOperation<T,32,8,1,4>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
  else {PackedLanesOperation<T,32,4,1,4>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}}
 if(s.f32&&s.routed&&!s.row_major&&routed_rows()){
  // OWNRT_SMALLK_ROWS=1|2: rows per subgroup for columns <= 640 (same per-row arithmetic); default 4.
  static const int small_k=[]{const char* e=std::getenv("OWNRT_SMALLK_ROWS");return e?std::atoi(e):4;}();
  if(s.columns<=640&&small_k==2){PackedRowsOperation<T,2>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
  if(s.columns<=640&&small_k==1){PackedRowsOperation<T,1>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
  PackedRowsOperation<T,4>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
#endif
 if(s.f32){PackedOperation<T,true>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
 PackedOperation<T>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
// integrated::Matrix facade: caller must explicitly admit raw packed storage.
// Cache pointer tables/expanded layouts are not accepted by this interface.
inline integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,InputMode input,Storage storage){auto s=validate(d,m,input,storage);switch(unsigned(m.type)){case 12:return issue<12>(d,m,s);case 13:return issue<13>(d,m,s);case 18:return issue<18>(d,m,s);case 23:return issue<23>(d,m,s);case 42:return issue<42>(d,m,s);}throw std::invalid_argument("unreachable GSQ type");}
} // namespace gsqn
