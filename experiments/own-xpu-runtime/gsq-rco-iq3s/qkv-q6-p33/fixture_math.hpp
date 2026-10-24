#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet6-kopt/reference.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/p28/dense.hpp"
namespace p33 {
template<iq3::Type T,unsigned K>
inline float dense_lane(const uint8_t* __restrict w,const uint16_t* __restrict x,
 unsigned begin,unsigned end,unsigned lane) {
 static_assert(T==iq3::Type::Q6_K || T==iq3::Type::Q8_0 ||
               T==iq3::Type::F32 || T==iq3::Type::BF16);
 static_assert(K>0 && K<=17408 && K%iq3::layout(T).elements==0);
 if(begin%256)return p28::dense_lane<T,K>(w,x,begin,end,lane);
 float sum=0;
 for(unsigned tile=begin+lane*8;tile<end;tile+=256){
  if constexpr(T==iq3::Type::Q6_K || T==iq3::Type::Q8_0){
   constexpr unsigned group=T==iq3::Type::Q6_K?16:32;
   const float scale=iq3::bits_float(iq3::u32(w+K+4*(tile/group)));
   #pragma unroll
   for(unsigned j=0;j<8;++j)if(tile+j<end){
    float value=scale*float(iq3::signed8(w[tile+j]));
    float input=iq3::bits_float(uint32_t(x[tile+j])<<16);
    float product=value*input;sum=sum+product;
   }
  }else{
   #pragma unroll
   for(unsigned j=0;j<8;++j)if(tile+j<end){
    float value=iq3::decode(T,w+(tile+j)*iq3::layout(T).bytes,0);
    float input=iq3::bits_float(uint32_t(x[tile+j])<<16);
    float product=value*input;sum=sum+product;
   }
  }
 }
 return sum;
}

}
