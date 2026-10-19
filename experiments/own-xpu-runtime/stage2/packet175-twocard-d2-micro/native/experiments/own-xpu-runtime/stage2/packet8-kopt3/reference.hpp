#pragma once
#include "decode.hpp"
#include <vector>
namespace iq3::kopt3 {
// Read-only bindings may be shared by gate and up. No write can alias any
// other binding, including a read or another output/workspace/status.
inline void validate_aliases(const std::vector<std::pair<uint64_t,bool>>& accesses) {
 for(size_t i=0;i<accesses.size();++i)for(size_t j=0;j<i;++j)
  if(accesses[i].first==accesses[j].first && (accesses[i].second || accesses[j].second))
   throw std::invalid_argument("aliased writable bindings");
}
// Arithmetic v1: exactly packet7 SG32 / split4, with no FMA contraction.
enum class Variant { constant, slm, constant_split4, slm_split4 };
inline const char* name(Variant v){switch(v){
 case Variant::constant:return "decode_const_sg32_v1";
 case Variant::slm:return "decode_slm_sg32_v1";
 case Variant::constant_split4:return "decode_const_split4_v1";
 case Variant::slm_split4:return "decode_slm_split4_v1";
 }throw std::invalid_argument("variant");}
inline unsigned splits(Variant v){name(v);return v==Variant::constant_split4 || v==Variant::slm_split4?4:1;}
using kopt2::bounds;
inline float lane(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t begin,size_t end,unsigned l){
#define CASE(T) case Type::T:return dot<Type::T>(w,x,a,begin,end,l,ConstantTables{},HostShare{})
 switch(t){CASE(F32);CASE(F16);CASE(BF16);CASE(Q8_0);CASE(Q6_K);CASE(Q3_K);CASE(IQ3_XXS);CASE(IQ2_S);CASE(IQ3_S);CASE(IQ4_NL);}
#undef CASE
 throw std::invalid_argument("type");
}
inline float row(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t k,Variant v){
 unsigned n=splits(v);float partial[4]{};
 for(unsigned s=0;s<n;++s){auto [begin,end]=bounds(k,s,n);float sums[32]{};
  for(unsigned l=0;l<32;++l)sums[l]=lane(t,w,x,a,begin,end,l);
  partial[s]=tree32(sums);
 }
 for(unsigned width=1;width<n;width*=2)for(unsigned s=0;s<n;s+=2*width)partial[s]=partial[s]+partial[s+width];
 return partial[0];
}
}
