#pragma once
#include <sycl/sycl.hpp>
#include "fused.hpp"
namespace p39 {
inline uint32_t sticky_load(Bound b){return sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).load();}
inline void sticky_fail(Bound b){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}
template<Kind E> inline void device_tail(Bound b,unsigned row,uint16_t first,uint16_t second){
 if(!*b.active||sticky_load(b))return;
 if(!position_valid<E>(b)){sticky_fail(b);return;}
 row_tail<E>(b,row,first,second);
}
template<class F> F guarded(F f){static_assert(sizeof(F)<=1024);return f;}
template<Type T,unsigned K,Kind E,bool Fused,unsigned Split> class GemvKernel;
template<Type T,unsigned K,Kind E,bool Fused,unsigned Split> class FinishKernel;
// Preserve the selected p28.dense.rows4 dispatch, including its existing
// local-memory allocation and unconditional work-group barrier. Split four
// finishes inside this kernel; it never acquires a new separate finish launch.
template<Type T,unsigned K,Kind E,bool Fused,unsigned Split> class Rows4GemvKernel;
template<Type T,unsigned K,Kind E,bool Fused,unsigned Split>
std::vector<sycl::event> gemv_rows4(sycl::queue& q,Bound b,std::vector<sycl::event> deps){
 constexpr unsigned wg=128*Split;
 auto e=q.submit([&](sycl::handler& h){h.depends_on(deps);sycl::local_accessor<float,1> partial(4*2*4,h);
  h.parallel_for<Rows4GemvKernel<T,K,E,Fused,Split>>(sycl::nd_range<1>(size_t((b.rows*b.count+3)/4)*wg,wg),guarded([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id();unsigned item=unsigned(it.get_group_linear_id())*4*Split+sub,logical=item/Split,part=item%Split;
   bool active=logical<b.rows*b.count;std::array<float,2> values{};
   if(active){auto bounds=iq3::kopt2::bounds(K,part,Split);values=lanes<T,K,E>(b,logical*b.rb,0,lane,unsigned(bounds.first),unsigned(bounds.second));}
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,values[0],(lane+width)%32);if(lane%(2*width)==0)values[0]=values[0]+rhs;}
   if(active&&lane==0){if constexpr(Split==1){uint16_t a=iq3::bf16_bits(values[0]);b.y[logical]=a;if constexpr(Fused)device_tail<E>(b,logical,a,0);}else partial[(sub/Split)*8+part]=values[0];}
   it.barrier(sycl::access::fence_space::local_space);
   if(active&&lane==0&&part==0){
    if constexpr(Split==4){unsigned off=(sub/Split)*8;uint16_t a=iq3::bf16_bits((partial[off]+partial[off+1])+(partial[off+2]+partial[off+3]));b.y[logical]=a;if constexpr(Fused)device_tail<E>(b,logical,a,0);}
   }
  }));});return {e};
}
template<Type T,unsigned K,Kind E,bool Fused,unsigned Split=1>
std::vector<sycl::event> gemv(sycl::queue& q,Bound b,std::vector<sycl::event> deps={}){
 static_assert(Split==1||Split==4);
 if constexpr(E==Kind::silu_div4||E==Kind::shared_act)return gemv_rows4<T,K,E,Fused,Split>(q,b,deps);
 else {
 constexpr bool routed=E==Kind::expert_act||E==Kind::expert_checks||E==Kind::down_status;
 static_assert(!routed||Split==1);
 auto e=q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for<GemvKernel<T,K,E,Fused,Split>>(sycl::nd_range<1>(size_t(b.rows)*b.count*Split*32,32),guarded([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
  auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),item=unsigned(it.get_group_linear_id()),logical=item/Split,part=item%Split,row=logical%b.rows,slot=logical/b.rows;
  iq3::Route route{0,0,b.rows};if constexpr(routed)route=b.routes[slot];bool ok=iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
  std::array<float,2> v{};
  if(valid){auto bounds=iq3::kopt2::bounds(K,part,Split);unsigned source=(route.expert_id*b.rows+route.row_begin+row)*b.rb;v=lanes<T,K,E>(b,source,slot,lane,unsigned(bounds.first),unsigned(bounds.second));}
  constexpr unsigned projections=(E==Kind::expert_act||E==Kind::expert_checks)?2:1;
  for(unsigned j=0;j<projections;++j)for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,v[j],(lane+width)%32);if(lane%(2*width)==0)v[j]=v[j]+rhs;}
  // Check all routes only for activation, after the GEMV and its reduction.
  // No validity predicate stays live across the dot-product loop. Down has
  // no gated output, so its own row-zero status writer can set sticky directly.
  bool valid_all=true;
  if constexpr(Fused&&E==Kind::expert_act){bool lane_ok=lane>=b.count||iq3::valid_route(b.routes[lane],b.experts,b.rows,b.rows);valid_all=sycl::all_of_group(sg,lane_ok);}
  if(lane==0){
   if constexpr(Split==4){b.scratch[logical*8+part]=valid?v[0]:iq3::bits_float(0x7fc00000);}
   else {uint16_t a=iq3::bf16_bits(valid?v[0]:iq3::bits_float(0x7fc00000));uint16_t c=iq3::bf16_bits(valid?v[1]:iq3::bits_float(0x7fc00000));b.y[logical]=a;
    if constexpr(E==Kind::expert_act||E==Kind::expert_checks)b.py[logical]=c;
    if constexpr(Fused){if constexpr(E==Kind::down_status||E==Kind::expert_checks){if(row==0&&!ok&&*b.active)sticky_fail(b);}else if constexpr(E==Kind::expert_act){if(*b.active){if(!valid_all)sticky_fail(b);else device_tail<E>(b,logical,a,c);}}else device_tail<E>(b,logical,a,c);}
   }
   if constexpr(routed)if(row==0){b.status[slot]=!ok;if constexpr(E==Kind::expert_act||E==Kind::expert_checks)b.peer_status[slot]=!ok;}
  }
 }));});
 std::vector<sycl::event> out{e};
 if constexpr(Split==4){auto f=q.submit([&](sycl::handler& h){h.depends_on(e);h.parallel_for<FinishKernel<T,K,E,Fused,Split>>(sycl::range<1>(b.rows*b.count),guarded([=](sycl::id<1> id){unsigned j=unsigned(id[0]);auto v=b.scratch+j*8;uint16_t a=iq3::bf16_bits((v[0]+v[1])+(v[2]+v[3]));b.y[j]=a;if constexpr(Fused)device_tail<E>(b,j,a,0);}));});out.push_back(f);}
 return out;
 }
}
} // namespace p39
// Unfused tails use the source-bound packet29 runtime bodies below.
#include "runtime_baseline.hpp"
namespace p39 {
template<Type T,unsigned K,Kind E,bool Fused,unsigned Split=1>
std::vector<sycl::event> chain(sycl::queue& q,Bound b,std::vector<sycl::event> deps={}){
 validate<T,K,E,Split>(b);
 auto events=gemv<T,K,E,Fused,Split>(q,b,deps);
 if constexpr(!Fused){events.push_back(runtime_tail<E,0>(q,b,{events.back()}));if constexpr(E==Kind::expert_act||E==Kind::expert_checks||E==Kind::shared_combine)events.push_back(runtime_tail<E,1>(q,b,{events.back()}));if constexpr(E==Kind::expert_act)events.push_back(runtime_tail<E,2>(q,b,{events.back()}));}
 return events;
}
} // namespace p39
