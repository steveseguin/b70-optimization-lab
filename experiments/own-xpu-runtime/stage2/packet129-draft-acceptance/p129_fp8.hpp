#pragma once
#include "mtp_kernels.hpp"
#include "p28/dense.hpp"
#include "specialised.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p129 {
using Linear=mtp36::Linear;
using ownrt::Allocation;using integrated::Launch;
template<class F> F checked(F f){static_assert(sizeof(F)<=1024,"draft capture exceeds 1024 bytes");return f;}
struct Bound {const uint8_t *w,*peer;const uint16_t *x;uint16_t *y,*py;const iq3::Route *route;uint32_t *status,*ps;unsigned rows,batch,experts;};
static_assert(sizeof(Bound)<=1024);
inline float decode(uint8_t b) {
 unsigned e=(b>>3)&15,m=b&7;
 float value=e?iq3::bits_float(((e+120)<<23)|(m<<20)):float(m)*(1.f/512.f);
 return b&128?-value:value;
}
template<unsigned K,bool Int8> inline float lane(const uint8_t* w,const uint16_t* x,unsigned l){
 if constexpr(!Int8)return p28::dense_lane<iq3::Type::BF16,K>(w,x,0,K,l);
 else {float sum=0;for(unsigned tile=l*8;tile<K;tile+=256)for(unsigned k=tile;k<std::min(tile+8,K);++k){
  const auto* s=w+K+(k/128)*2;
  float scale=iq3::bits_float((uint32_t(s[0])|(uint32_t(s[1])<<8))<<16);
  float value=decode(w[k])*scale;
  float product=value*iq3::bits_float(uint32_t(x[k])<<16);sum=sum+product;
 }return sum;}
}
template<unsigned K,bool Int8,bool Pair> struct Dense final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 Linear a;Bound bind(std::span<void*const> p)const{return {static_cast<const uint8_t*>(p[0]),static_cast<const uint8_t*>(p[1]),static_cast<const uint16_t*>(p[2]),static_cast<uint16_t*>(p[3]),static_cast<uint16_t*>(p[4]),a.routes?static_cast<const iq3::Route*>(p[5]):nullptr,static_cast<uint32_t*>(p[6]),static_cast<uint32_t*>(p[7]),a.rows,a.batch,a.experts};}
 static constexpr size_t rb=Int8?K+2*((K+127)/128):K*2;
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
static void extent(ownrt::Device& d,Allocation a,size_t n){auto r=d.arena.row(a);if(!r.live||r.bytes<n||r.memory!=ownrt::Memory::device)throw std::invalid_argument("draft allocation extent");}
template<unsigned K,bool I,bool Pair> Launch issue(ownrt::Device& d,const Linear& a){Dense<K,I,Pair> op;op.a=a;std::array<Allocation,8> ids{a.w,Pair?a.peer:a.w,a.x,a.y,Pair?a.py:a.y,a.routes?a.routes:a.x,a.status?a.status:a.y,a.ps?a.ps:a.y};auto e=d.compute(op,ids,{});return {e,e,1};}
template<unsigned K> Launch typed(ownrt::Device& d,const Linear& a){if(a.int8)return a.paired?issue<K,true,true>(d,a):issue<K,true,false>(d,a);return a.paired?issue<K,false,true>(d,a):issue<K,false,false>(d,a);}
inline Launch linear(ownrt::Device& d,const Linear& a){
 if(!a.rows||!a.batch||a.batch>10||!a.experts||a.experts>512||a.rows>248320||(!a.routes&&a.experts!=1)||(a.paired&&!a.routes))throw std::invalid_argument("draft linear geometry");
 size_t rb=a.int8?a.columns+2*((a.columns+127)/128):a.columns*2;
 extent(d,a.w,size_t(a.experts)*a.rows*rb);extent(d,a.x,size_t(a.paired?1:a.batch)*a.columns*2);extent(d,a.y,size_t(a.batch)*a.rows*2);
 if(a.routes){extent(d,a.routes,a.batch*sizeof(iq3::Route));extent(d,a.status,a.batch*4);}if(a.paired){extent(d,a.peer,size_t(a.experts)*a.rows*rb);extent(d,a.py,size_t(a.batch)*a.rows*2);extent(d,a.ps,a.batch*4);}
 switch(a.columns){
#define K(n) case n:return typed<n>(d,a)
 K(4);K(8);K(16);K(64);K(320);K(640);K(2560);K(6144);K(10240);
#undef K
 default:throw std::invalid_argument("draft uncompiled K");}
}
}
