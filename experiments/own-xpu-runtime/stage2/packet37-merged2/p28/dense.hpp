#pragma once
#include "../../packet10-kopt5/expanded.hpp"

// Original packet28 spelling of packet10's dense arithmetic. No device APIs.
namespace p28 {
using iq3::Type;

template<Type T, unsigned K>
inline float dense_lane(const uint8_t* w, const uint16_t* x,
                        unsigned begin, unsigned end, unsigned lane) {
  static_assert(T==Type::Q6_K || T==Type::Q8_0 || T==Type::F32 ||
                T==Type::BF16 || T==Type::F16);
  static_assert(K && K<=17408 && K%iq3::layout(T).elements==0);
  float sum=0;
  // All numerical indices in this loop are 32-bit. Pointer address formation
  // is native-width, but no 64-bit code word is loaded or shifted.
  for(unsigned tile=begin+lane*8;tile<end;tile+=256) {
    unsigned stop=tile+8<end?tile+8:end;
    if constexpr(T==Type::Q6_K || T==Type::Q8_0) {
      constexpr unsigned group=T==Type::Q6_K?16:32;
      // Production starts are multiples of 256; group and tile sizes are
      // multiples of eight. Thus every production tile needs exactly one
      // segment. Splitting here also preserves arbitrary unaligned ranges.
      for(unsigned first=tile;first<stop;) {
        unsigned boundary=(first/group+1)*group;
        unsigned last=boundary<stop?boundary:stop;
        const uint8_t* sp=w+K+4*(first/group);
        uint32_t bits=uint32_t(sp[0])|(uint32_t(sp[1])<<8)|
                      (uint32_t(sp[2])<<16)|(uint32_t(sp[3])<<24);
        const float scale=iq3::bits_float(bits);
        const bool exceptional=(bits&0x7f800000u)==0x7f800000u;
        if(exceptional) {
          // Keep the exact old per-weight expression on exceptional scales.
          // Q6/Q8 never had the IQ NaN-sign special case in expanded::value.
          for(unsigned i=first;i<last;++i) {
            float value=iq3::expanded::value(T,w,K,i);
            float input=iq3::bits_float(uint32_t(x[i])<<16);
            float product=value*input;
            sum=sum+product;
          }
        } else {
          for(unsigned i=first;i<last;++i) {
            float value=scale*float(iq3::signed8(w[i]));
            float input=iq3::bits_float(uint32_t(x[i])<<16);
            float product=value*input;
            sum=sum+product;
          }
        }
        first=last;
      }
    } else {
      for(unsigned i=tile;i<stop;++i) {
        float value=iq3::decode(T,w+i*iq3::layout(T).bytes,0);
        float input=iq3::bits_float(uint32_t(x[i])<<16);
        float product=value*input;
        sum=sum+product;
      }
    }
  }
  return sum;
}

template<Type T,unsigned K>
inline float dense_row(const uint8_t* w,const uint16_t* x,unsigned split) {
  if(split!=1 && split!=4)throw std::invalid_argument("packet28 dense split");
  float partial[4]{};
  for(unsigned p=0;p<split;++p) {
    auto bounds=iq3::kopt2::bounds(K,p,split);
    float lanes[32];
    for(unsigned lane=0;lane<32;++lane)
      lanes[lane]=dense_lane<T,K>(w,x,unsigned(bounds.first),unsigned(bounds.second),lane);
    partial[p]=iq3::tree32(lanes);
  }
  return split==1?partial[0]:(partial[0]+partial[1])+(partial[2]+partial[3]);
}
}
