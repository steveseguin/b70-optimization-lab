#pragma once
// Original packet46 CPU implementation. SIMD lanes are independent GPU logical
// lanes, never independent partial sums of one GPU lane. No SYCL/device include.
#include "../../packet45-merged3/p39_fused.hpp"
#include "../../packet45-merged3/p42_expert.hpp"
#include <immintrin.h>
#include <array>
#include <cfenv>
#include <cmath>
#include <span>

namespace p46cpu {
using iq3::Type;
inline constexpr unsigned hidden=2560, intermediate=640;
template<size_t N> consteval auto words(const std::array<uint8_t,N>& bytes) {
 std::array<int,N> out{};for(size_t i=0;i<N;++i)out[i]=bytes[i];return out;
}
inline constexpr auto iq2_words=words(p28::iq2_bytes);
inline constexpr auto iq3_words=words(p28::iq3s_bytes);
inline constexpr int iq4_levels[16]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};

inline void require_environment() {
 if(std::fegetround()!=FE_TONEAREST || (_mm_getcsr()&((1u<<15)|(1u<<6))))
  throw std::runtime_error("CPU expert requires round-to-nearest, FTZ=0, DAZ=0");
}
inline bool finite(uint16_t bits){return (bits&0x7f80)!=0x7f80;}

// Pure bit widening and permutation. Each AVX load visits eight consecutive
// logical SG32 lanes at the SAME j; no floating-point operation is reordered.
template<unsigned K> struct Input {
 static_assert(K%8==0);
 alignas(32) std::array<float,((K+255)/256)*256> tiled{};
 explicit Input(const uint16_t* source) {
  for(unsigned k=0;k<K;++k){unsigned tile=k/256,lane=(k%256)/8,j=k%8;
   tiled[tile*256+j*32+lane]=iq3::bits_float(uint32_t(source[k])<<16);}
 }
};

template<Type T,unsigned K> inline std::array<float,32> lanes(const uint8_t* row,const Input<K>& input) {
 static_assert(((T==Type::IQ2_S||T==Type::IQ3_S)&&K==2560) || (T==Type::IQ4_NL&&K==640));
 std::array<float,32> result{};
 for(unsigned first=0;first<32;first+=8){
  __m256 sum=_mm256_setzero_ps();
  for(unsigned tile=0;tile<K;tile+=256){
   // K640's last sixteen inactive lanes perform NO add, even of +0.
   if(tile+first*8>=K)continue;
   alignas(32) float scales[8];
   alignas(32) int index0[8],index1[8],signs[8];
   for(unsigned v=0;v<8;++v){unsigned k=tile+8*(first+v);
    if constexpr(T==Type::IQ2_S||T==Type::IQ3_S){
     const auto* b=row+(k/256)*iq3::layout(T).bytes;unsigned i=k%256;
     float d=iq3::half(iq3::u16(b));
     if constexpr(T==Type::IQ2_S){unsigned q=i/8;
      index0[v]=(b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8))*8;
      signs[v]=b[34+q];scales[v]=(d*(0.5f+float((b[74+i/32]>>(4*((i/16)%2)))&15)))*0.25f;
     }else{unsigned q=i/4;
      index0[v]=(b[2+q]|(((b[66+q/8]>>(q%8))&1)<<8))*4;++q;
      index1[v]=(b[2+q]|(((b[66+q/8]>>(q%8))&1)<<8))*4;
      signs[v]=b[74+i/8];scales[v]=d*float(1+2*((b[106+i/64]>>(4*((i/32)%2)))&15));
     }
    }else{const auto* b=row+(k/32)*18;scales[v]=iq3::half(iq3::u16(b));}
   }
   const __m256 scale=_mm256_load_ps(scales);
   for(unsigned j=0;j<8;++j){__m256i level;
    if constexpr(T==Type::IQ2_S||T==Type::IQ3_S){
     const __m256i index=_mm256_add_epi32(_mm256_load_si256(reinterpret_cast<const __m256i*>(T==Type::IQ2_S||j<4?index0:index1)),_mm256_set1_epi32(T==Type::IQ2_S?j:j%4));
     __m256i magnitude=_mm256_i32gather_epi32(T==Type::IQ2_S?iq2_words.data():iq3_words.data(),index,4);
     __m256i sign=_mm256_and_si256(_mm256_srlv_epi32(_mm256_load_si256(reinterpret_cast<const __m256i*>(signs)),_mm256_set1_epi32(j)),_mm256_set1_epi32(1));
     __m256i mask=_mm256_sub_epi32(_mm256_setzero_si256(),sign);
     level=_mm256_sub_epi32(_mm256_xor_si256(magnitude,mask),mask);
    }else{
     alignas(32) int codes[8];
     for(unsigned v=0;v<8;++v){unsigned k=tile+8*(first+v)+j;const auto* b=row+(k/32)*18;codes[v]=(b[2+k%16]>>(4*((k%32)/16)))&15;}
     level=_mm256_i32gather_epi32(iq4_levels,_mm256_load_si256(reinterpret_cast<const __m256i*>(codes)),4);
    }
    const __m256 value=_mm256_mul_ps(scale,_mm256_cvtepi32_ps(level));
    const __m256 product=_mm256_mul_ps(value,_mm256_load_ps(input.tiled.data()+tile+j*32+first));
    sum=_mm256_add_ps(sum,product);
   }
  }
  _mm256_storeu_ps(result.data()+first,sum);
 }
 return result;
}
template<Type T,unsigned K> inline float dot(const uint8_t* row,const Input<K>& input){
 auto sums=lanes<T,K>(row,input);return iq3::tree32(sums.data());
}
struct Output {
 std::array<uint16_t,intermediate> gate{},up{},activation{};
 std::array<uint16_t,hidden> down{};
 bool operator==(const Output&)const=default;
};
struct Expert {
 Type format=Type::IQ2_S;
 std::vector<uint8_t> gate,up,down;
 unsigned gate_stride()const{return format==Type::IQ2_S?820:1100;}
 size_t bytes()const{return gate.size()+up.size()+down.size();}
 bool shape_valid()const{return (format==Type::IQ2_S||format==Type::IQ3_S)&&gate.size()==size_t(intermediate)*gate_stride()&&up.size()==gate.size()&&down.size()==size_t(hidden)*360;}
 void validate()const{
  if(!shape_valid())
   throw std::invalid_argument("CPU expert shape/format");
  // One-time immutable weight admission, outside timed decode. Nonfinite
  // rejection is this candidate's unsupported-input guard, NOT a claim that
  // the existing device oracle has the same exceptional-output semantics.
  for(const auto* bank:{&gate,&up,&down}){unsigned stride=bank==&down?18:iq3::layout(format).bytes;
   for(size_t i=0;i<bank->size();i+=stride)if((iq3::u16(bank->data()+i)&0x7c00)==0x7c00)
    throw std::invalid_argument("nonfinite packed scale unsupported");}
 }
};
template<Type T> inline void calculate(const Expert& weights,const uint16_t* x,Output& out){
 const Input<hidden> input(x);constexpr unsigned rb=T==Type::IQ2_S?820:1100;
 for(unsigned row=0;row<intermediate;++row){
  out.gate[row]=iq3::bf16_bits(dot<T,hidden>(weights.gate.data()+size_t(row)*rb,input));
  out.up[row]=iq3::bf16_bits(dot<T,hidden>(weights.up.data()+size_t(row)*rb,input));
  out.activation[row]=p39::activation(out.gate[row],out.up[row]);
 }
 const Input<intermediate> activation(out.activation.data());
 for(unsigned row=0;row<hidden;++row)out.down[row]=iq3::bf16_bits(dot<Type::IQ4_NL,intermediate>(weights.down.data()+size_t(row)*360,activation));
}
// Candidate standalone request boundary. Invalid/unsupported data poisons this
// CPU request and leaves caller-visible output untouched. It is intentionally
// not wired into the model: device exceptional/status parity is still pending.
inline bool execute(const Expert& weights,const std::array<uint16_t,hidden>& x,Output& output,uint32_t& sticky,bool active=true){
 if(!active||sticky)return false;
 if(!weights.shape_valid()){sticky=1;return false;}
 for(auto value:x)if(!finite(value)){sticky=1;return false;}
 Output candidate;
 if(weights.format==Type::IQ2_S)calculate<Type::IQ2_S>(weights,x.data(),candidate);
 else if(weights.format==Type::IQ3_S)calculate<Type::IQ3_S>(weights,x.data(),candidate);
 else{sticky=1;return false;}
 for(auto* buffer:{&candidate.gate,&candidate.up,&candidate.activation})for(auto v:*buffer)if(!finite(v)){sticky=1;return false;}
 for(auto v:candidate.down)if(!finite(v)){sticky=1;return false;}
 output=candidate;return true;
}
} // namespace p46cpu
