#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/p49b_expert_kernel.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build-snapshot/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/prepared_submission.hpp"
#endif
#line 1
#pragma once
// Lab-authored production-context adapter; packet48 owns the arithmetic/layout.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build-snapshot/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/p49b_gemv.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build-snapshot/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/p39_fused.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build-snapshot/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
namespace p49b {
using iq3::Type;
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
template<Type T,unsigned K>struct Kernel final:Base {
 unsigned rows,count,experts;
 static constexpr bool paired=T==Type::IQ2_S;
 static constexpr bool routed=paired||T==Type::IQ4_NL;
 p39::Bound bind(std::span<void*const>p)const {
  p39::Bound b{};b.rows=rows;b.count=count;b.experts=experts;b.rb=p49bgemv::layout(T,K).row_bytes;
  b.w=static_cast<const uint8_t*>(p[0]);b.peer=static_cast<const uint8_t*>(p[1]);
  b.x=static_cast<const uint16_t*>(p[2]);b.y=static_cast<uint16_t*>(p[3]);b.py=static_cast<uint16_t*>(p[4]);
  b.routes=static_cast<const iq3::Route*>(p[5]);b.status=static_cast<uint32_t*>(p[6]);b.peer_status=static_cast<uint32_t*>(p[7]);
  b.error=static_cast<uint32_t*>(p[16]);b.active=static_cast<const uint32_t*>(p[17]);return b;
 }
 static std::array<float,2> lane(p39::Bound b,size_t source,unsigned slot,unsigned l) {
  if constexpr(paired)return p49bgemv::gate_lane<T,K>(b.w+source*b.rb,b.peer+source*b.rb,b.x,0,K,l);
  else return {p49bgemv::lane<T,K>(b.w+source*b.rb,b.x+(T==Type::IQ4_NL?slot*K:0),0,K,l),0};
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {
  auto b=bind(p);
  for(unsigned slot=0;slot<count;++slot){iq3::Route r{0,0,rows};if constexpr(routed)r=b.routes[slot];bool ok=iq3::valid_route(r,experts,rows,rows);
   if constexpr(routed){b.status[slot]=!ok;if constexpr(paired)b.peer_status[slot]=!ok;if(!ok&&*b.active&&!*b.error)*b.error=1;}
   #pragma omp parallel for num_threads(2) schedule(static)
   for(unsigned row=0;row<rows;++row){bool valid=ok&&row<r.row_count;float values[2][32]{};
    if(valid)for(unsigned l=0;l<32;++l){auto v=lane(b,size_t(r.expert_id)*rows+r.row_begin+row,slot,l);values[0][l]=v[0];values[1][l]=v[1];}
    b.y[slot*rows+row]=iq3::bf16_bits(valid?iq3::tree32(values[0]):iq3::bits_float(0x7fc00000));
    if constexpr(paired)b.py[slot*rows+row]=iq3::bf16_bits(valid?iq3::tree32(values[1]):iq3::bits_float(0x7fc00000));
   }
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {
  auto b=bind(p);return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(size_t(b.rows)*b.count*32,32)](sycl::handler& h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id(),logical=it.get_group_linear_id(),row=logical%b.rows,slot=logical/b.rows;
   iq3::Route r{0,0,b.rows};if constexpr(routed)r=b.routes[slot];bool ok=iq3::valid_route(r,b.experts,b.rows,b.rows),valid=ok&&row<r.row_count;
   std::array<float,2> v{};if(valid)v=lane(b,size_t(r.expert_id)*b.rows+r.row_begin+row,slot,l);
   for(unsigned p=0;p<(paired?2u:1u);++p)for(unsigned w=1;w<32;w*=2){float x=sycl::select_from_group(sg,v[p],(l+w)%32);if(l%(2*w)==0)v[p]=v[p]+x;}
   if(!l){b.y[logical]=iq3::bf16_bits(valid?v[0]:iq3::bits_float(0x7fc00000));if constexpr(paired)b.py[logical]=iq3::bf16_bits(valid?v[1]:iq3::bits_float(0x7fc00000));
    if constexpr(routed)if(!row){b.status[slot]=!ok;if constexpr(paired)b.peer_status[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
   }
  }));});
 }
#endif
};
}
