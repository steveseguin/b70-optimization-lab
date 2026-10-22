#pragma once
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string_view>
namespace p58xd {
inline uint64_t drm_size(std::string_view value) {
  while(!value.empty() && (value.front()==' ' || value.front()=='\t')) value.remove_prefix(1);
  while(!value.empty() && (value.back()==' ' || value.back()=='\t')) value.remove_suffix(1);
  auto bad=[](){throw std::runtime_error("DRM occupancy malformed or overflow");};
  uint64_t n=0;size_t i=0;
  for(;i<value.size() && value[i]>='0' && value[i]<='9';++i) {
    const auto digit=uint64_t(value[i]-'0');
    if(n>(std::numeric_limits<uint64_t>::max()-digit)/10) bad();
    n=n*10+digit;
  }
  if(!i) bad();
  const auto unit=value.substr(i);uint64_t scale=1;
  if(unit==" KiB")scale=1024;
  else if(unit==" MiB")scale=1024*1024;
  else if(!unit.empty())bad();
  if(n>std::numeric_limits<uint64_t>::max()/scale)bad();
  return n*scale;
}
}
