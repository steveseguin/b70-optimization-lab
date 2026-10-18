#pragma once
#include "mtp_kernels.hpp"
#include "p104_layout.hpp"
#include "p28/dense.hpp"
#include "specialised.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p104mtp {
using Linear=mtp36::Linear;
using ownrt::Allocation;using integrated::Launch;
template<class F> F checked(F f){static_assert(sizeof(F)<=1024,"draft capture exceeds 1024 bytes");return f;}
struct Bound {const uint8_t *w,*peer;const uint16_t *x;uint16_t *y,*py;const iq3::Route *route;uint32_t *status,*ps;unsigned rows,batch,experts;};
static_assert(sizeof(Bound)<=1024);
template<unsigned K,bool Int8> inline float lane(const uint8_t* w,const uint16_t* x,unsigned l,size_t source=0){
 if constexpr(!Int8){float sum=0;
  for(unsigned tile=l*8;tile<K;tile+=256){unsigned stop=tile+8<K?tile+8:K;
   for(unsigned k=tile;k<stop;++k){float value=iq3::decode(iq3::Type::BF16,p104::draft_address<K,false>(w,source,k*2),0);float input=iq3::bits_float(uint32_t(x[k])<<16);float product=value*input;sum=sum+product;}
  }return sum;}
 else {float sum=0;for(unsigned tile=l*8;tile<K;tile+=256)for(unsigned k=tile;k<std::min(tile+8,K);++k){
  const auto* s=p104::draft_address<K,true>(w,source,K+(k/16)*4);uint32_t u=uint32_t(s[0])|(uint32_t(s[1])<<8)|(uint32_t(s[2])<<16)|(uint32_t(s[3])<<24);
  float value=iq3::bits_float(u)*float(iq3::signed8(*p104::draft_address<K,true>(w,source,k)));float product=value*iq3::bits_float(uint32_t(x[k])<<16);sum=sum+product;}return sum;}
}
template<unsigned K,bool Int8,bool Pair> struct Dense final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 Linear a;Bound bind(std::span<void*const> p)const{return {static_cast<const uint8_t*>(p[0]),static_cast<const uint8_t*>(p[1]),static_cast<const uint16_t*>(p[2]),static_cast<uint16_t*>(p[3]),static_cast<uint16_t*>(p[4]),a.routes?static_cast<const iq3::Route*>(p[5]):nullptr,static_cast<uint32_t*>(p[6]),static_cast<uint32_t*>(p[7]),a.rows,a.batch,a.experts};}
 static constexpr size_t rb=Int8?K+4*((K+15)/16):K*2;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto b=bind(p);
  #pragma omp parallel for num_threads(2) schedule(static)
  for(unsigned i=0;i<b.rows*b.batch;++i){unsigned slot=i/b.rows,row=i%b.rows;auto r=b.route?b.route[slot]:iq3::Route{0,0,b.rows};bool valid=iq3::valid_route(r,b.experts,b.rows,b.rows)&&row<r.row_count;
   if(row==0&&b.route){b.status[slot]=!valid;if constexpr(Pair)b.ps[slot]=!valid;}
   float sums[2][32]{};if(valid)for(unsigned l=0;l<32;++l){size_t off=(size_t(r.expert_id)*b.rows+r.row_begin+row);auto x=b.x+(Pair?0:size_t(slot)*K);sums[0][l]=lane<K,Int8>(b.w,x,l,off);if constexpr(Pair)sums[1][l]=lane<K,Int8>(b.peer,x,l,off);}
   b.y[i]=iq3::bf16_bits(valid?iq3::tree32(sums[0]):iq3::bits_float(0x7fc00000));if constexpr(Pair)b.py[i]=iq3::bf16_bits(valid?iq3::tree32(sums[1]):iq3::bits_float(0x7fc00000));
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto b=bind(p);size_t n=size_t(b.rows)*b.batch;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(((n+3)/4)*128,128),checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id();size_t i=it.get_global_linear_id()/32;if(i>=n)return;unsigned slot=i/b.rows,row=i%b.rows;
   auto r=b.route?b.route[slot]:iq3::Route{0,0,b.rows};bool valid=iq3::valid_route(r,b.experts,b.rows,b.rows)&&row<r.row_count;float sum=0,peer=0;
   if(valid){size_t off=(size_t(r.expert_id)*b.rows+r.row_begin+row);auto x=b.x+(Pair?0:size_t(slot)*K);sum=lane<K,Int8>(b.w,x,l,off);if constexpr(Pair)peer=lane<K,Int8>(b.peer,x,l,off);}
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(l+width)%32);float pr=sycl::select_from_group(sg,peer,(l+width)%32);if(l%(2*width)==0){sum=sum+rhs;peer=peer+pr;}}
   if(l==0){b.y[i]=iq3::bf16_bits(valid?sum:iq3::bits_float(0x7fc00000));if constexpr(Pair)b.py[i]=iq3::bf16_bits(valid?peer:iq3::bits_float(0x7fc00000));if(row==0&&b.route){b.status[slot]=!valid;if constexpr(Pair)b.ps[slot]=!valid;}}
  }));});
 }
#endif
};
}
