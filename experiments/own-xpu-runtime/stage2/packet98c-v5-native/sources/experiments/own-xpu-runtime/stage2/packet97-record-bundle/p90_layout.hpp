#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet97-record-bundle/p90_layout.hpp"
#pragma once
// Exact immutable weight decoding; no activation or accumulation arithmetic.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet98c-v5-native/sources/experiments/own-xpu-runtime/stage2/packet97-record-bundle/p49b_gemv.hpp"
namespace p90 {
inline constexpr size_t expert_stride(unsigned k){return p49bgemv::layout(iq3::Type::IQ2_S,k).halves+4*(k/256);}
inline void expert_repack(unsigned k,const uint8_t*src,uint8_t*dst){
 const auto l=p49bgemv::layout(iq3::Type::IQ2_S,k);
 std::vector<uint8_t> base(l.row_bytes);
 p49bgemv::repack_row(iq3::Type::IQ2_S,k,src,base.data());
 std::memcpy(dst,base.data(),l.halves);
 for(unsigned b=0;b<k/256;++b){float d=iq3::half(p49bgemv::load16(base.data()+l.halves+2*b));std::memcpy(dst+l.halves+4*b,&d,4);}
}
inline constexpr size_t hc_stride=320*4;
inline std::vector<uint8_t> hc_from_expanded(const uint8_t*src,size_t rows){
 const size_t rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 std::vector<uint8_t> out(rows*hc_stride);
 for(size_t r=0;r<rows;++r)for(unsigned k=0;k<320;++k){
  uint32_t bits=p49bgemv::load32(src+r*rb+320+4*(k/32));
  if((bits&0x7f800000u)==0x7f800000u)throw std::invalid_argument("p90 nonfinite HC weight scale");
  float scale=iq3::bits_float(bits);
  float value=scale*float(iq3::signed8(src[r*rb+k]));
  std::memcpy(out.data()+r*hc_stride+4*k,&value,4);
 }return out;
}
inline std::vector<uint8_t> hc_repack(const uint8_t*src,size_t bytes){
 const auto expanded=iq3::expanded::expand(iq3::Type::Q8_0,src,bytes,320);
 return hc_from_expanded(expanded.data(),expanded.size()/iq3::expanded::row_bytes(iq3::Type::Q8_0,320));
}
} // namespace p90
