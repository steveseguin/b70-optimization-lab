#pragma once
// Original packet55 implementation. Read-only lab headers provide the format
// tables, half/BF16 conversions and deterministic SiLU, not a CPU GEMV body.
#include "../../packet49c-round2/p39_fused.hpp"
#include <immintrin.h>
#include <array>
#include <cfenv>
#include <stdexcept>
#include <vector>

namespace p55cpu {
using iq3::Type;
constexpr unsigned hidden=2560, intermediate=640, vector_rows=8;
template<size_t N> consteval auto widen_table(const std::array<uint8_t,N>& source) {
 std::array<int,N> out{};for(size_t i=0;i<N;++i)out[i]=source[i];return out;
}
inline constexpr auto iq2=widen_table(p28::iq2_bytes);
inline constexpr auto iq3s=widen_table(p28::iq3s_bytes);
inline constexpr int levels[]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
inline void require_environment(){
 if(std::fegetround()!=FE_TONEAREST||(_mm_getcsr()&((1u<<15)|(1u<<6))))
  throw std::runtime_error("requires round-nearest, gradual underflow, FTZ=DAZ=0");
}
inline bool finite(uint16_t b){return (b&0x7f80)!=0x7f80;}
struct Output {
 std::array<uint16_t,intermediate> gate{},up{},activation{};
 std::array<uint16_t,hidden> down{};
 bool operator==(const Output&)const=default;
};
struct Expert {
 Type format=Type::IQ2_S;
 std::vector<uint8_t> gate,up,down;
 size_t stride()const{return format==Type::IQ2_S?820:1100;}
 size_t bytes()const{return gate.size()+up.size()+down.size();}
 bool shape_valid()const{return (format==Type::IQ2_S||format==Type::IQ3_S)&&gate.size()==intermediate*stride()&&up.size()==gate.size()&&down.size()==hidden*360;}
 void validate()const{
  if(!shape_valid())
   throw std::invalid_argument("invalid expert format/extent");
  for(const auto* p:{&gate,&up,&down}){
   const unsigned block=p==&down?18:iq3::layout(format).bytes;
   for(size_t i=0;i<p->size();i+=block)if((iq3::u16(p->data()+i)&0x7c00)==0x7c00)
    throw std::invalid_argument("nonfinite weight scale refused before execution");
  }
 }
};

// A register lane is always an output row. Logical GPU lanes are separate
// registers, so no horizontal SIMD operation changes any row's sum order.
// The optional lane capture exists only for exactness fixtures.
template<Type T,unsigned K> inline void dot8(const uint8_t* weights,const uint16_t* input,
                                            float* result,float* capture=nullptr){
 constexpr unsigned block=iq3::layout(T).elements, bytes=iq3::layout(T).bytes;
 constexpr unsigned stride=K/block*bytes;
 __m256 sums[32];
 for(unsigned lane=0;lane<32;++lane){
  __m256 sum=_mm256_setzero_ps();
  for(unsigned k=lane*8;k<K;k+=256){
   alignas(32) float scales[8];alignas(32) int indices[8],next[8],signs[8];
   const unsigned i=k%block;
   for(unsigned row=0;row<8;++row){
    const uint8_t* b=weights+row*stride+(k/block)*bytes;
    const float d=iq3::half(iq3::u16(b));
    if constexpr(T==Type::IQ2_S){
     const unsigned q=i/8;indices[row]=(b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8))*8;
     signs[row]=b[34+q];scales[row]=(d*(0.5f+float((b[74+i/32]>>(4*((i/16)%2)))&15)))*0.25f;
    }else if constexpr(T==Type::IQ3_S){
     unsigned q=i/4;indices[row]=(b[2+q]|(((b[66+q/8]>>(q%8))&1)<<8))*4;++q;
     next[row]=(b[2+q]|(((b[66+q/8]>>(q%8))&1)<<8))*4;
     signs[row]=b[74+i/8];scales[row]=d*float(1+2*((b[106+i/64]>>(4*((i/32)%2)))&15));
    }else {static_assert(T==Type::IQ4_NL);scales[row]=d;}
   }
   const __m256 scale=_mm256_load_ps(scales);
   for(unsigned j=0;j<8;++j){
    __m256i magnitude;
    if constexpr(T==Type::IQ4_NL){
     alignas(32) int codes[8];
     for(unsigned row=0;row<8;++row){const uint8_t* b=weights+row*stride+(k/block)*bytes;codes[row]=(b[2+(i+j)%16]>>(4*((i+j)/16)))&15;}
     magnitude=_mm256_i32gather_epi32(levels,_mm256_load_si256(reinterpret_cast<const __m256i*>(codes)),4);
    }else {
     const __m256i base=_mm256_load_si256(reinterpret_cast<const __m256i*>(T==Type::IQ2_S||j<4?indices:next));
     const __m256i index=_mm256_add_epi32(base,_mm256_set1_epi32(T==Type::IQ2_S?j:j%4));
     magnitude=_mm256_i32gather_epi32(T==Type::IQ2_S?iq2.data():iq3s.data(),index,4);
     const __m256i sign=_mm256_and_si256(_mm256_srlv_epi32(_mm256_load_si256(reinterpret_cast<const __m256i*>(signs)),_mm256_set1_epi32(j)),_mm256_set1_epi32(1));
     const __m256i negative=_mm256_sub_epi32(_mm256_setzero_si256(),sign);
     magnitude=_mm256_sub_epi32(_mm256_xor_si256(magnitude,negative),negative);
    }
    const __m256 value=_mm256_mul_ps(scale,_mm256_cvtepi32_ps(magnitude));
    const __m256 x=_mm256_set1_ps(iq3::bits_float(uint32_t(input[k+j])<<16));
    const __m256 product=_mm256_mul_ps(value,x);
    sum=_mm256_add_ps(sum,product);
   }
  }
  sums[lane]=sum;if(capture)_mm256_storeu_ps(capture+lane*8,sum);
 }
 // Adjacent SG32 tree, exactly widths 1,2,4,8,16. No padded final-tile adds.
 for(unsigned width=1;width<32;width*=2)for(unsigned lane=0;lane<32;lane+=2*width)
  sums[lane]=_mm256_add_ps(sums[lane],sums[lane+width]);
 _mm256_storeu_ps(result,sums[0]);
}
template<Type T> inline void gate_rows(const Expert& e,const uint16_t* x,Output& out,unsigned row){
 alignas(32) float gate[8],up[8];
 dot8<T,hidden>(e.gate.data()+row*e.stride(),x,gate);
 dot8<T,hidden>(e.up.data()+row*e.stride(),x,up);
 for(unsigned r=0;r<8;++r){
  out.gate[row+r]=iq3::bf16_bits(gate[r]);out.up[row+r]=iq3::bf16_bits(up[r]);
  // Deliberately use the lab's normative deterministic SiLU (explicit FMAs
  // inside detmath only), with separate gate/up and activation BF16 boundaries.
  out.activation[row+r]=p39::activation(out.gate[row+r],out.up[row+r]);
 }
}
inline void down_rows(const Expert& e,Output& out,unsigned row){
 alignas(32) float values[8];dot8<Type::IQ4_NL,intermediate>(e.down.data()+row*360,out.activation.data(),values);
 for(unsigned r=0;r<8;++r)out.down[row+r]=iq3::bf16_bits(values[r]);
}
inline void calculate(const Expert& e,const uint16_t* x,Output& out){
 for(unsigned row=0;row<intermediate;row+=8){if(e.format==Type::IQ2_S)gate_rows<Type::IQ2_S>(e,x,out,row);else gate_rows<Type::IQ3_S>(e,x,out,row);}
 for(unsigned row=0;row<hidden;row+=8)down_rows(e,out,row);
}
inline bool finite_output(const Output& out){
 for(auto p:{&out.gate,&out.up,&out.activation})for(auto v:*p)if(!finite(v))return false;
 for(auto v:out.down)if(!finite(v))return false;return true;
}
// Transaction boundary, NOT a replacement for production route/status logic.
// Reject exceptional requests without publishing partial results. Raw dot8 is
// separately compared for nonfinite inputs; full device exception parity is open.
inline bool execute(const Expert& e,const std::array<uint16_t,hidden>& x,Output& out,uint32_t& error,bool active=true){
 if(!active||error)return false;
 if(!e.shape_valid()){error=1;return false;}
 for(auto v:x)if(!finite(v)){error=1;return false;}
 Output tmp;calculate(e,x.data(),tmp);if(!finite_output(tmp)){error=1;return false;}out=tmp;return true;
}
} // namespace p55cpu
