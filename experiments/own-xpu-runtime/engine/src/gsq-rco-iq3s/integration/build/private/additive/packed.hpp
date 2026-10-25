#pragma once
// An additive Engine overlay may supply its own internally consistent checked
// runtime header closure before including this facade.
#ifndef GSQN_RUNTIME_HEADERS_PROVIDED
#error "Engine runtime closure required"
#endif
#include "device_formats.hpp"
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
inline constexpr uint32_t max_tokens=64;
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
   for(size_t k=lane;k<b.s.columns;k+=32){const float input=x[k];
    #pragma unroll
    for(unsigned i=0;i<R;++i){const size_t row=first+i;if(!valid||row>=b.s.rows||row>=r.row_count)continue;
     const auto*w=b.w+(size_t(r.expert_id)*b.s.rows+r.row_begin+row)*b.s.row_bytes;
     const float weight=gsq::element_unchecked(T,w+(k/elements)*bytes,k%elements);const float product=weight*input;acc[i]=acc[i]+product;}}
   #pragma unroll
   for(unsigned i=0;i<R;++i){float sum=acc[i];
    for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
    const size_t row=first+i;
    if(lane==0&&row<b.s.rows)reinterpret_cast<float*>(b.y)[size_t(slot)*b.s.rows+row]=valid&&row<r.row_count?sum:iq3::bits_float(0x7fc00000);}
   if(lane==0&&first==0&&b.status)b.status[slot]=!valid;
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
 if(s.f32&&s.routed&&!s.row_major&&routed_rows()){PackedRowsOperation<T,4>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
#endif
 if(s.f32){PackedOperation<T,true>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
 PackedOperation<T>op;op.s=s;auto e=d.compute(op,ids,{});return {e,e,1};}
// integrated::Matrix facade: caller must explicitly admit raw packed storage.
// Cache pointer tables/expanded layouts are not accepted by this interface.
inline integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,InputMode input,Storage storage){auto s=validate(d,m,input,storage);switch(unsigned(m.type)){case 12:return issue<12>(d,m,s);case 13:return issue<13>(d,m,s);case 18:return issue<18>(d,m,s);case 23:return issue<23>(d,m,s);case 42:return issue<42>(d,m,s);}throw std::invalid_argument("unreachable GSQ type");}
} // namespace gsqn
