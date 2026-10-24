#pragma once
// An additive Engine overlay may supply its own internally consistent checked
// runtime header closure before including this facade.
#ifndef GSQN_RUNTIME_HEADERS_PROVIDED
#ifdef OWN_RT_HOST_ONLY
#include "../../stage2/packet205-host-row-capture/host_backend.hpp"
#include "../../stage2/packet181-session-swap-v3/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/performance.hpp"
#else
#include "../../stage2/packet208-sycl-paired-projections/selected_headers.hpp"
#endif
#endif // GSQN_RUNTIME_HEADERS_PROVIDED
#include "device_formats.hpp"
#include <array>
namespace gsqn {
enum class InputMode {shared,per_slot};
enum class Storage {packed_direct};
inline void require(bool b,const char*s){if(!b)throw std::invalid_argument(s);}
inline size_t multiply(size_t a,size_t b){require(!b||a<=SIZE_MAX/b,"GSQ extent overflow");return a*b;}
struct Shape {size_t rows,columns,row_bytes;uint32_t count,experts;bool routed,per_slot;};
struct Bound {Shape s;const uint8_t*w;const uint16_t*x;uint16_t*y;const iq3::Route*routes;uint32_t*status;};
template<unsigned T> inline float lane_sum(const Bound&b,const iq3::Route&r,size_t row,unsigned slot,unsigned lane){
 constexpr size_t elements=T==42?64:256;constexpr size_t bytes=T==42?18:T==12?144:T==13?176:T==23?136:98;
 const auto*w=b.w+(size_t(r.expert_id)*b.s.rows+r.row_begin+row)*b.s.row_bytes;
 const auto*x=b.x+(b.s.per_slot?size_t(slot)*b.s.columns:0);float sum=0;
 for(size_t k=lane;k<b.s.columns;k+=32){const float weight=gsq::element_unchecked(T,w+(k/elements)*bytes,k%elements);const float product=weight*iq3::bits_float(uint32_t(x[k])<<16);sum=sum+product;}
 return sum;
}
template<unsigned T> class PackedKernel;
template<unsigned T> struct PackedOperation final:
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
   for(size_t row=0;row<s.rows;++row){float sums[32]{};const bool active=valid&&row<r.row_count;if(active)for(unsigned lane=0;lane<32;++lane)sums[lane]=lane_sum<T>(b,r,row,slot,lane);b.y[size_t(slot)*s.rows+row]=iq3::bf16_bits(active?iq3::tree32(sums):iq3::bits_float(0x7fc00000));}
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  require(q.has_property<sycl::property::queue::in_order>(),"GSQ requires selected ordered queue");
  const auto b=bind(p);
  // Outer command owns by-value pointers/shape/dependencies. No caller span or
  // operation object survives by reference in the prepared callback.
  return ownrt::prepared_submit(q,[=](sycl::handler&h){h.depends_on(deps);h.parallel_for<PackedKernel<T>>(sycl::nd_range<1>(b.s.rows*b.s.count*32,32),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   const auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();const size_t logical=it.get_group_linear_id(),row=logical%b.s.rows;const unsigned slot=logical/b.s.rows;
   const auto r=b.routes?b.routes[slot]:iq3::Route{0,0,uint32_t(b.s.rows)};const bool valid=iq3::valid_route(r,b.s.experts,uint32_t(b.s.rows),uint32_t(b.s.rows)),active=valid&&row<r.row_count;
   float sum=active?lane_sum<T>(b,r,row,slot,lane):0.f;
   for(unsigned width=1;width<32;width*=2){const float rhs=sycl::select_from_group(sg,sum,(lane+width)%32);if(lane%(2*width)==0)sum=sum+rhs;}
   if(lane==0){b.y[logical]=iq3::bf16_bits(active?sum:iq3::bits_float(0x7fc00000));if(row==0&&b.status)b.status[slot]=!valid;}
  }));});
 }
#endif
};
inline Shape validate(ownrt::Device&d,const integrated::Matrix&m,InputMode input,Storage storage){
 require(input==InputMode::shared||input==InputMode::per_slot,"GSQ input mode");
 require(storage==Storage::packed_direct,"GSQ packed direct storage only");const auto t=unsigned(m.type);require(t==12||t==13||t==18||t==23||t==42,"GSQ unsupported packed type");
 require(m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16&&!m.fp32,"GSQ BF16 activation/output only");
 require(m.rows&&m.rows<=248320&&m.columns&&m.columns<=10240&&m.count&&m.count<=10&&m.experts&&m.experts<=512,"GSQ geometry bound");
 require(!m.span||m.span==m.rows,"GSQ full route span only");
 const bool routed=bool(m.routes);require(routed?bool(m.status):(m.count==1&&m.experts==1&&!m.status&&input==InputMode::shared),"GSQ routes/status identity");
 const size_t rb=gsq::row_bytes(t,m.columns);Shape s{m.rows,m.columns,rb,m.count,m.experts,routed,input==InputMode::per_slot};
 std::array<ownrt::Allocation,5> ids{m.w,m.x,m.y,m.routes,m.status};
 const size_t sizes[]{multiply(multiply(m.rows,m.experts),rb),multiply(multiply(m.columns,s.per_slot?m.count:1),2),multiply(multiply(m.rows,m.count),2),multiply(m.count,sizeof(iq3::Route)),multiply(m.count,4)};
 const size_t alignment[]{1,2,2,alignof(iq3::Route),4};
 for(size_t i=0;i<(routed?5:3);++i){require(ids[i]!=0,"GSQ null binding");const auto&r=d.arena.row(ids[i]);require(r.live&&r.memory==ownrt::Memory::device&&r.bytes>=sizes[i]&&uintptr_t(r.pointer)%alignment[i]==0,"GSQ live extent/alignment");for(size_t j=0;j<i;++j)require(ids[i]!=ids[j],"GSQ distinct operand allocations required");}
 return s;
}
template<unsigned T> inline integrated::Launch issue(ownrt::Device&d,const integrated::Matrix&m,Shape s){PackedOperation<T>op;op.s=s;std::array<ownrt::Allocation,5>ids{m.w,m.x,m.y,m.routes?m.routes:m.x,m.status?m.status:m.y};auto e=d.compute(op,ids,{});return {e,e,1};}
// integrated::Matrix facade: caller must explicitly admit raw packed storage.
// Cache pointer tables/expanded layouts are not accepted by this interface.
inline integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,InputMode input,Storage storage){auto s=validate(d,m,input,storage);switch(unsigned(m.type)){case 12:return issue<12>(d,m,s);case 13:return issue<13>(d,m,s);case 18:return issue<18>(d,m,s);case 23:return issue<23>(d,m,s);case 42:return issue<42>(d,m,s);}throw std::invalid_argument("unreachable GSQ type");}
} // namespace gsqn
