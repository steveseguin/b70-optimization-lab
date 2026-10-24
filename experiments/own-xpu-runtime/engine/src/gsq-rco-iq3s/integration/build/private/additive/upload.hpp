#pragma once
// Own-runtime host upload conversion. This does not change source descriptors,
// apply gain offsets, or change target precision: F16/BF16 values widen exactly.
// Consistent private iq3 definitions supplied by Engine.
#include <cstring>
#include <span>
#include <stdexcept>
#include <vector>
namespace gsq::controls {
inline size_t source_width(uint32_t type) {
  if (type == 0) return 4;
  if (type == 1 || type == 30) return 2;
  throw std::invalid_argument("nonfloating primitive control");
}
inline std::vector<uint8_t> upload_f32(uint32_t type, std::span<const uint8_t> raw) {
  const size_t width=source_width(type);
  if(raw.empty() || raw.size()%width || raw.size()>4*1024*1024)
    throw std::invalid_argument("unaligned or oversized primitive upload chunk");
  if(type==0) return {raw.begin(),raw.end()};
  std::vector<uint8_t> out(raw.size()*2);
  for(size_t i=0;i<raw.size()/2;++i){
    const uint16_t bits=iq3::u16(raw.data()+i*2);
    const float value=type==1?iq3::half(bits):iq3::bits_float(uint32_t(bits)<<16);
    std::memcpy(out.data()+i*4,&value,4);
  }
  return out;
}
} // namespace gsq::controls
