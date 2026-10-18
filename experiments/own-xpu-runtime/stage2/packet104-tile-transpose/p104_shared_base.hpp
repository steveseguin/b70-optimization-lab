#pragma once
#include "p33_submit.hpp"
#include "p33_candidates.hpp"
#include "p42_expert.hpp"
#include "expert_down.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p104sharedbase {
using namespace p33;
template<unsigned Mode,iq3::Type T,unsigned K,unsigned Split=1> struct Kernel final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 p28::Bound b{};
 p28::Bound bind(std::span<void*const> p)const {auto d=b;d.w=static_cast<const uint8_t*>(p[0]);d.peer=static_cast<const uint8_t*>(p[1]);d.x=static_cast<const uint16_t*>(p[2]);d.y=static_cast<uint16_t*>(p[3]);d.py=static_cast<uint16_t*>(p[4]);d.routes=b.has_routes?static_cast<const iq3::Route*>(p[5]):nullptr;d.status=static_cast<uint32_t*>(p[6]);d.ps=static_cast<uint32_t*>(p[7]);d.scratch=static_cast<float*>(p[8]);return d;}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {
  auto d=bind(p);
  for(unsigned slot=0;slot<d.count;++slot){
   auto r=d.routes?d.routes[slot]:iq3::Route{0,0,d.rows};
   bool ok=iq3::valid_route(r,d.experts,d.rows,d.rows);
   if(d.routes){d.status[slot]=!ok;if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S)d.ps[slot]=!ok;}
   #pragma omp parallel for num_threads(2) schedule(static) if(d.rows>=64)
   for(unsigned row=0;row<d.rows;++row){
    bool valid=ok&&row<r.row_count;float parts[2][4]{};
    for(unsigned part=0;part<Split;++part){
     float sums[2][32]{};auto range=iq3::kopt2::bounds(K,part,Split);
     if(valid)for(unsigned lane=0;lane<32;++lane){
      const unsigned source=(r.expert_id*d.rows+r.row_begin+row)*unsigned(d.rb);
      if constexpr(T==iq3::Type::IQ4_NL)sums[0][lane]=down_lane<Mode,K>(d.w+source,d.x+slot*K,lane);
      else if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S){auto pair=Mode==2?p42expert::gate_lane<T,K>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane):expert_lane<T,K,true>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane);sums[0][lane]=pair[0];sums[1][lane]=pair[1];}
      else sums[0][lane]=dense_lane<T,K>(d.w+source,d.x,unsigned(range.first),unsigned(range.second),lane);
     }
     for(unsigned j=0;j<(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S?2:1);++j)parts[j][part]=iq3::tree32(sums[j]);
    }
    for(unsigned j=0;j<(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S?2:1);++j){float v=Split==1?parts[j][0]:(parts[j][0]+parts[j][1])+(parts[j][2]+parts[j][3]);(j?d.py:d.y)[slot*d.rows+row]=iq3::bf16_bits(valid?v:iq3::bits_float(0x7fc00000));}
   }
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto d=bind(p);
  const size_t groups=size_t(d.rows)*d.count*Split;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(groups*32,32),p28::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),item=unsigned(it.get_group_linear_id()),logical=item/Split,part=item%Split;
   const unsigned row=logical%d.rows,slot=logical/d.rows;
   iq3::Route r{0,0,d.rows};if(d.routes)r=d.routes[slot];const bool ok=iq3::valid_route(r,d.experts,d.rows,d.rows),valid=ok&&row<r.row_count;
   std::array<float,2> sums{};
   if(valid){const unsigned source=(r.expert_id*d.rows+r.row_begin+row)*unsigned(d.rb);auto range=iq3::kopt2::bounds(K,part,Split);
    if constexpr(T==iq3::Type::IQ4_NL)sums[0]=down_lane<Mode,K>(d.w+source,d.x+slot*K,lane);
    else if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S)sums=Mode==2?p42expert::gate_lane<T,K>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane):expert_lane<T,K,true>(d.w+source,d.peer+source,d.x,unsigned(range.first),unsigned(range.second),lane);
    else sums[0]=dense_lane<T,K>(d.w+source,d.x,unsigned(range.first),unsigned(range.second),lane);
   }
   constexpr unsigned projections=T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S?2:1;
   for(unsigned j=0;j<projections;++j){for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sums[j],(lane+width)%32);if(lane%(2*width)==0)sums[j]=sums[j]+rhs;}
    if(lane==0){float v=valid?sums[j]:iq3::bits_float(0x7fc00000);if constexpr(Split==1)(j?d.py:d.y)[logical]=iq3::bf16_bits(v);else d.scratch[(logical*2+j)*4+part]=v;}}
   if(lane==0&&row==0&&part==0&&d.routes){d.status[slot]=!ok;if constexpr(projections==2)d.ps[slot]=!ok;}
  }));});
 }
#endif
};
}
