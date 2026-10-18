#pragma once
#include "mtp_kernels.hpp"
#include "p28/dense.hpp"
#include "specialised.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p108 {
using Linear=mtp36::Linear;
using ownrt::Allocation;using integrated::Launch;
template<class F> F checked(F f){static_assert(sizeof(F)<=1024,"draft capture exceeds 1024 bytes");return f;}
struct Bound {const uint8_t *w,*peer;const uint16_t *x;uint16_t *y,*py;const iq3::Route *route;uint32_t *status,*ps;unsigned rows,batch,experts;};
static_assert(sizeof(Bound)<=1024);
template<unsigned K,bool Int8> inline float lane(const uint8_t* w,const uint16_t* x,unsigned l){
 if constexpr(!Int8)return p28::dense_lane<iq3::Type::BF16,K>(w,x,0,K,l);
 else {
  static_assert(K==640||K==2560,"packet108 INT8 production shapes only");
  float sum=0;
  for(unsigned tile=l*8;tile<K;tile+=256){
   // Eight contiguous values have one original FP32 scale (groups of 16).
   // Only raw loads change. The scale*code, value*x and sum additions retain
   // their original types, order and rounding boundaries, including NaNs.
   uint32_t scale_bits;std::memcpy(&scale_bits,w+K+(tile/16)*4,4);
   uint32_t words[2];
#if defined(__SYCL_DEVICE_ONLY__)
   sycl::vec<uint32_t,2> codes;
   codes.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(w+tile)));
   words[0]=codes[0];words[1]=codes[1];
   sycl::vec<uint16_t,8> inputs;
   inputs.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+tile));
#else
   std::memcpy(words,w+tile,8);
#endif
   for(unsigned j=0;j<8;++j){
    const uint8_t code=uint8_t(words[j/4]>>(8*(j%4)));
    float value=iq3::bits_float(scale_bits)*float(iq3::signed8(code));
#if defined(__SYCL_DEVICE_ONLY__)
    uint16_t bits=inputs[j];
#else
    uint16_t bits=x[tile+j];
#endif
    float product=value*iq3::bits_float(uint32_t(bits)<<16);sum=sum+product;
   }
  }
  return sum;
 }
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
   float sums[2][32]{};if(valid)for(unsigned l=0;l<32;++l){size_t off=(size_t(r.expert_id)*b.rows+r.row_begin+row)*rb;auto x=b.x+(Pair?0:size_t(slot)*K);sums[0][l]=lane<K,Int8>(b.w+off,x,l);if constexpr(Pair)sums[1][l]=lane<K,Int8>(b.peer+off,x,l);}
   b.y[i]=iq3::bf16_bits(valid?iq3::tree32(sums[0]):iq3::bits_float(0x7fc00000));if constexpr(Pair)b.py[i]=iq3::bf16_bits(valid?iq3::tree32(sums[1]):iq3::bits_float(0x7fc00000));
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto b=bind(p);size_t n=size_t(b.rows)*b.batch;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(((n+3)/4)*128,128),checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id();size_t i=it.get_global_linear_id()/32;if(i>=n)return;unsigned slot=i/b.rows,row=i%b.rows;
   auto r=b.route?b.route[slot]:iq3::Route{0,0,b.rows};bool valid=iq3::valid_route(r,b.experts,b.rows,b.rows)&&row<r.row_count;float sum=0,peer=0;
   if(valid){size_t off=(size_t(r.expert_id)*b.rows+r.row_begin+row)*rb;auto x=b.x+(Pair?0:size_t(slot)*K);sum=lane<K,Int8>(b.w+off,x,l);if constexpr(Pair)peer=lane<K,Int8>(b.peer+off,x,l);}
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(l+width)%32);float pr=sycl::select_from_group(sg,peer,(l+width)%32);if(l%(2*width)==0){sum=sum+rhs;peer=peer+pr;}}
   if(l==0){b.y[i]=iq3::bf16_bits(valid?sum:iq3::bits_float(0x7fc00000));if constexpr(Pair)b.py[i]=iq3::bf16_bits(valid?peer:iq3::bits_float(0x7fc00000));if(row==0&&b.route){b.status[slot]=!valid;if constexpr(Pair)b.ps[slot]=!valid;}}
  }));});
 }
#endif
};
}
