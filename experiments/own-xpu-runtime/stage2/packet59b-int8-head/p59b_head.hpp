#pragma once
#include "performance.hpp"
#include <cfenv>
namespace p59b {
// Separate signed-byte rows and one FP32 maximum/127 scale per row.
// Input is the exact decoded target Q6 weight, never a modified target tensor.
inline void quantize(const float* values, unsigned columns, int8_t* codes, float& scale) {
 if(!columns || columns>17408 || std::fegetround()!=FE_TONEAREST)
  throw std::invalid_argument("p59b quantizer geometry/rounding");
 float maximum=0;
 for(unsigned k=0;k<columns;++k){if(!std::isfinite(values[k]))throw std::invalid_argument("p59b nonfinite head");maximum=std::max(maximum,std::abs(values[k]));}
 scale=maximum==0?1.f:maximum/127.f;
 if(!(scale>0) || !std::isfinite(scale))throw std::invalid_argument("p59b unrepresentable row scale");
 for(unsigned k=0;k<columns;++k)codes[k]=int8_t(std::clamp(int(std::nearbyint(values[k]/scale)),-127,127));
}
// Fixed striped sums and fixed tree; the scale multiplies the final FP32 sum.
inline float lane(const int8_t* w,const uint16_t* x,unsigned columns,unsigned l) {
 float sum=0;
 for(unsigned tile=l*8;tile<columns;tile+=256)
  for(unsigned j=0;j<8 && tile+j<columns;++j){float product=float(w[tile+j])*iq3::bits_float(uint32_t(x[tile+j])<<16);sum=sum+product;}
 return sum;
}
struct Head {ownrt::Allocation codes{},scales{},x{},y{};unsigned rows{},columns{};};
integrated::Launch head(ownrt::Device&,const Head&);
}
