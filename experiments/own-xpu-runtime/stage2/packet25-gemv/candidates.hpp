#pragma once
#include "arithmetic.hpp"
#include <array>
#include <string>
#ifndef HOST_ONLY
#include <sycl/sycl.hpp>
#endif
namespace p25 {
using namespace iq3;
enum class C { current, rows4, wg32, private_decode, paired_input, half_table, staged, scale8, wide8 };
inline const char* name(C c){switch(c){
#define N(x) case C::x:return #x
N(current);N(rows4);N(wg32);N(private_decode);N(paired_input);N(half_table);N(staged);N(scale8);N(wide8);
#undef N
}throw std::invalid_argument("candidate");}
inline constexpr bool expert(Type t){return t==Type::IQ2_S||t==Type::IQ3_S||t==Type::IQ3_XXS||t==Type::IQ4_NL;}
inline std::vector<C> candidates(Type t){
 if(t==Type::IQ4_NL)return {C::current,C::rows4,C::wg32,C::private_decode,C::wide8,C::staged};
 if(expert(t))return {C::current,C::rows4,C::wg32,C::private_decode,C::paired_input,C::half_table,C::staged};
 return {C::current,C::rows4,C::scale8,C::wide8};
}
inline unsigned rows_per_group(C c,unsigned split){return c==C::rows4?(split==1?4:2):1;}
inline unsigned local_size(C c,unsigned split){return c==C::current?128:32*split*rows_per_group(c,split);}
inline float input(uint16_t x){return bits_float(uint32_t(x)<<16);}
template<class U> inline void load8(const U* src,U* dst){
#ifndef HOST_ONLY
 sycl::vec<U,8> v;v.load(0,sycl::multi_ptr<const U,sycl::access::address_space::global_space>(src));
 for(unsigned j=0;j<8;++j)dst[j]=v[j];
#else
 for(unsigned j=0;j<8;++j)dst[j]=src[j];
#endif
}
// Does not change the scale expression, weight product, input product or sum.
// No two blocks are prefetched or pipelined, no SLM/register grid is created.
template<Type T> inline void half_decode(const uint8_t* w,const float* ds,size_t i,float* v){
 constexpr auto f=layout(T);const auto b=w+i/f.elements*f.bytes;unsigned n=i%f.elements;
 float d=ds[i/f.elements];
 if((std::bit_cast<uint32_t>(d)&0x7f800000)==0x7f800000){for(unsigned j=0;j<8;++j)v[j]=element(T,w,i+j);return;}
 float s=d;
 if constexpr(T==Type::IQ2_S)s=(d*(0.5f+float((b[74+n/32]>>(4*((n/16)%2)))&15)))*0.25f;
 if constexpr(T==Type::IQ3_S)s=d*float(1+2*((b[106+n/64]>>(4*((n/32)%2)))&15));
 if constexpr(T==Type::IQ3_XXS)s=(d*(0.5f+float(u32(b+66+4*(n/32))>>28)))*0.5f;
 for(unsigned j=0;j<8;++j)v[j]=s*float(expanded::quant(T,b,n+j));
}
template<Type T> inline void expanded8(const uint8_t* w,size_t k,size_t i,float* v,bool wide){
 uint8_t q[8];if(wide)load8(w+i,q);
 float s=bits_float(u32(w+expanded::codes_size(T,k)+4*(i/expanded::group_size(T))));
 for(unsigned j=0;j<8;++j){
  if constexpr(T==Type::IQ2_S||T==Type::IQ3_S||T==Type::IQ3_XXS){
   if((std::bit_cast<uint32_t>(s)&0x7fffffff)>0x7f800000){v[j]=bits_float(std::bit_cast<uint32_t>(s)|0x00400000);continue;}}
  v[j]=s*float(signed8(wide?q[j]:w[i+j]));
 }
}
template<Type T,C V,class Tables,class Share>
inline std::array<float,2> lane(const uint8_t* w,const uint8_t* peer,const uint16_t* x,
 const float* ds,const float* pds,size_t k,size_t begin,size_t end,unsigned l,bool paired,Tables tables,Share share){
 std::array<float,2> sum{};
 if constexpr(V==C::current||V==C::rows4||V==C::wg32){
  for(unsigned p=0;p<(paired?2u:1u);++p){
   if constexpr(expert(T))sum[p]=kopt3::dot<T>(p?peer:w,x,Type::BF16,begin,end,l,tables,share);
   else sum[p]=expanded::lane(T,p?peer:w,x,Type::BF16,k,begin,end,l);
  }
  return sum;
 }
 // Baseline peer-outer ordering is retained except explicit paired-input arm.
 for(unsigned outer=0;outer<(paired&&V!=C::paired_input?2u:1u);++outer){
  for(size_t tile=begin;tile<end;tile+=256){size_t i=tile+l*8;float xv[8]{};
   for(unsigned j=0;j<8;++j)if(i+j<end)xv[j]=input(x[i+j]);
   for(unsigned inner=0;inner<(paired&&V==C::paired_input?2u:1u);++inner){
    unsigned p=V==C::paired_input?inner:outer;const auto row=p?peer:w;float values[8]{};
    if constexpr(!expert(T)||V==C::staged){
     if(i<end){if constexpr(V==C::scale8||V==C::wide8)expanded8<T>(row,k,i,values,V==C::wide8);
      else for(unsigned j=0;j<8&&i+j<end;++j)values[j]=expanded::value(T,row,k,i+j);}
    }else if constexpr(V==C::half_table){if(i<end)half_decode<T>(row,p?pds:ds,i,values);}
    else if constexpr(V==C::wide8&&T==Type::IQ4_NL){if(i<end){auto b=row+(i/32)*18;float s=half(u16(b));uint8_t bytes[8];load8(b+2+i%16,bytes);for(unsigned j=0;j<8;++j)values[j]=s*float(kopt3::iq4_levels[(bytes[j]>>(4*((i%32)/16)))&15]);}}
    else if constexpr(V==C::private_decode)kopt3::decode8<T>(row,i<end?i:tile,values,kopt3::ConstantTables{},kopt3::HostShare{});
    else kopt3::decode8<T>(row,i<end?i:tile,values,tables,share);
    for(unsigned j=0;j<8;++j)if(i+j<end){float product=values[j]*xv[j];sum[p]=sum[p]+product;}
   }
  }
 }
 return sum;
}
template<Type T,C V> inline std::array<float,2> host_row(const uint8_t* w,const uint8_t* peer,const uint16_t* x,
 const float* ds,const float* pds,size_t k,unsigned split,bool paired){
 float part[2][4]{};
 for(unsigned s=0;s<split;++s){auto [lo,hi]=kopt2::bounds(k,s,split);float lanes[2][32]{};
  for(unsigned l=0;l<32;++l){auto v=lane<T,V>(w,peer,x,ds,pds,k,lo,hi,l,paired,kopt3::ConstantTables{},kopt3::HostShare{});for(unsigned p=0;p<(paired?2u:1u);++p)lanes[p][l]=v[p];}
  for(unsigned p=0;p<(paired?2u:1u);++p)part[p][s]=tree32(lanes[p]);
 }
 std::array<float,2> out{};for(unsigned p=0;p<(paired?2u:1u);++p)out[p]=split==1?part[p][0]:(part[p][0]+part[p][1])+(part[p][2]+part[p][3]);return out;
}
// Independent scalar decoder plus original lane/tree order: no candidate helpers.
inline float scalar_reference(Type t,const uint8_t* packed,const uint16_t* x,size_t k,unsigned split){
 float ps[4]{};for(unsigned s=0;s<split;++s){auto [lo,hi]=kopt2::bounds(k,s,split);float a[32]{};
 for(unsigned l=0;l<32;++l)for(size_t tile=lo+l*8;tile<hi;tile+=256)for(unsigned j=0;j<8&&tile+j<hi;++j){float prod=element(t,packed,tile+j)*input(x[tile+j]);a[l]=a[l]+prod;}
 ps[s]=tree32(a);}return split==1?ps[0]:(ps[0]+ps[1])+(ps[2]+ps[3]);
}
[[gnu::noinline]] inline float reference(Type t,const uint8_t* packed,const uint16_t* x,size_t k,unsigned split){
 if(expert(t))return integrated::arithmetic::row(t,packed,x,k,split==4?4:2);
 auto e=expanded::expand(t,packed,k/layout(t).elements*layout(t).bytes,k);return integrated::arithmetic::row(t,e.data(),x,k,split==4?7:6);
}
inline bool exceptional(Type t,const uint8_t* packed,size_t bytes,const uint16_t* x,size_t nx){
 auto f=layout(t);for(size_t b=0;b<bytes;b+=f.bytes){auto at=b+(t==Type::Q6_K?208:0);if((u16(packed+at)&0x7c00)==0x7c00)return true;}
 // Conservative overflow guard: even max finite scales and K17408 cannot
 // overflow a float dot when every |BF16 x| < 2^64. Includes all NaNs/infs.
 for(size_t i=0;i<nx;++i)if((x[i]&0x7fff)>=0x5f80)return true;
 return false;
}
template<class F> inline auto select_type(Type t,F f){switch(t){
#define T(X) case Type::X:return f.template operator()<Type::X>()
 T(Q6_K);T(Q8_0);T(IQ2_S);T(IQ3_S);T(IQ3_XXS);T(IQ4_NL);
#undef T
 default:throw std::invalid_argument("unsupported type");}}
template<class F> inline auto select_candidate(C c,F f){switch(c){
#define V(X) case C::X:return f.template operator()<C::X>()
 V(current);V(rows4);V(wg32);V(private_decode);V(paired_input);V(half_table);V(staged);V(scale8);V(wide8);
#undef V
 }throw std::invalid_argument("candidate");}
}
