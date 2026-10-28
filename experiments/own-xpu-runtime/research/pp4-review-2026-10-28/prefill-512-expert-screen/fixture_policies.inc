// CPU-device bitwise test of the expert-grouped prefill tiles (prefill_experts.hpp) against host replicas of the existing
// routed kernels' per-lane sequences (iq3block BlockRows, gsqn PackedRows incl. Q2_0, kopt MultiplyBlockRows).
#include <sycl/sycl.hpp>
#include "stage2/packet2/kernels/math.hpp"
#include "gsq-rco-iq3s/integration/build/private/additive/device_formats.hpp"
#include "stage2/packet6-kopt/reference.hpp"
#include "stage2/packet194-expert-diet-engine/prefill_experts.hpp"
#include <bit>
#include <cstdio>
#include <cstring>
#include <functional>
#include <random>
#include <vector>
using namespace iq3;
// verbatim copy of iq3block::block_element_words
inline float block_element_words(const uint8_t*b,float d,unsigned group,unsigned lane){
 const auto*half_words=reinterpret_cast<const uint16_t*>(b+66+4*group);const uint32_t word=uint32_t(half_words[0])|uint32_t(half_words[1])<<16,code=(word>>(7*(lane/8)))&127;
 const auto mask=code|((std::popcount(code)%2)<<7);
 const int sign=(mask>>(lane%8))&1?-1:1;
 const uint32_t index=(uint32_t(reinterpret_cast<const uint16_t*>(b+2+group*8)[lane/8])>>(8*((lane/4)%2)))&255;
 const auto mag=(iq3::iq3_grid[index]>>(8*(lane%4)))&255;
 return (((d*(0.5f+float(word>>28)))*0.5f)*float(mag))*float(sign);
}
// policies as in prefill_experts_policies.hpp
struct Iq3Words {static void decode(const uint8_t* row,uint32_t step,unsigned lane,unsigned gv,float (&v)[8]){
 const uint8_t* packed=row+step*98u;const float d=iq3::half(iq3::u16(packed));
 for(unsigned g=0;g<8;++g)if(g<gv)v[g]=block_element_words(packed,d,g,lane);}};
template<unsigned T> struct Elem {static void decode(const uint8_t* row,uint32_t step,unsigned lane,unsigned gv,float (&v)[8]){
 constexpr uint32_t elements=T==42?64:256,bytes=T==42?18:T==12?144:T==13?176:T==23?136:98;
 for(unsigned g=0;g<8;++g)if(g<gv){const uint32_t k=step*256u+g*32u+lane;v[g]=gsq::element_unchecked(T,row+(k/elements)*bytes,k%elements);}}};
template<iq3::Type T> struct Kopt {static void decode8(const uint8_t* row,uint32_t k,float (&v)[8]){iq3::kopt::decode8<T>(row,k,v);}};
static float tree(float* s){for(unsigned w=1;w<32;w*=2)for(unsigned i=0;i<32;i+=2*w)s[i]=s[i]+s[i+w];return s[0];}
static uint16_t rhalf(std::mt19937& g){std::uniform_real_distribution<float> u(0.0005f,0.05f);sycl::half h=sycl::half(u(g));uint16_t b;std::memcpy(&b,&h,2);return b;}
// host lane references -------------------------------------------------------------------------------------------------
float ref_iq3(const uint8_t* w,const float* x,uint32_t K,unsigned lane){float acc=0;
 for(uint32_t block=0;block<K/256;++block){const auto*packed=w+block*98u;const float d=iq3::half(iq3::u16(packed));
  for(unsigned group=0;group<8;++group){const uint32_t k=block*256u+group*32u+lane;const float weight=block_element_words(packed,d,group,lane);const float product=weight*x[k];acc=acc+product;}}
 return acc;}
template<unsigned T> float ref_elem(const uint8_t* w,const float* x,uint32_t K,unsigned lane){float acc=0;
 constexpr uint32_t elements=T==42?64:256,bytes=T==42?18:T==12?144:T==13?176:T==23?136:98;
 if constexpr(T==42){
  for(uint32_t block=0;block<K/64u;++block){const float d=iq3::half(iq3::u16(w+block*18u));
   for(unsigned h=0;h<2;++h){const uint32_t e=lane+32u*h,k=block*64u+e;const float input=x[k];
    const unsigned code=(w[block*18u+2u+e/4u]>>(2*(e%4u)))&3;const float weight=float(int(code)-1)*d;const float product=weight*input;acc=acc+product;}}
 } else for(uint32_t k=lane;k<K;k+=32){const float input=x[k];const float weight=gsq::element_unchecked(T,w+(k/elements)*bytes,k%elements);const float product=weight*input;acc=acc+product;}
 return acc;}
template<iq3::Type T> float ref_kopt(const uint8_t* w,const float* x,uint32_t K,unsigned lane){float acc=0;uint32_t k=lane*8u;
 for(;k+8u<=K;k+=256u){float input[8];for(unsigned j=0;j<8;++j)input[j]=x[k+j];float values[8];iq3::kopt::decode8<T>(w,k,values);
  for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc=acc+product;}}
 return acc;}
// ---------------------------------------------------------------------------------------------------------------------
struct Case{const char* name;uint32_t rows,k,rb,experts;std::function<void(std::mt19937&,uint8_t*)> fill_row;std::function<float(const uint8_t*,const float*,uint32_t,unsigned)> ref;};
