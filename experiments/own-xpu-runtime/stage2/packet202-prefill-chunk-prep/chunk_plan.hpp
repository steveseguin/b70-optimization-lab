#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <stdexcept>
#include <vector>
namespace p202 {
struct Span {std::size_t start,count;bool final=false;};
struct ChunkPlan {std::vector<Span> spans;std::size_t final_position;};
inline ChunkPlan make_plan(std::size_t start,std::size_t input_count,std::size_t context=4096,std::size_t width=2) {
 if(!context||context>4096||!input_count||input_count>context||start>=input_count||(width!=1&&width!=2))
  throw std::invalid_argument("chunk range/width/context refused");
 ChunkPlan out{{},input_count-1};
 for(auto at=start;at<out.final_position;) {
  auto n=std::min({width,out.final_position-at,std::size_t(32-at%32)});
  out.spans.push_back({at,n,false});at+=n;
 }
 return out;
}
struct Region {std::uintptr_t address;std::size_t bytes,required;bool writable;};
inline void validate_bindings(std::span<const Region> regions) {
 for(auto a:regions)if(!a.address||!a.required||a.bytes<a.required||a.address>std::numeric_limits<std::uintptr_t>::max()-a.bytes)
  throw std::invalid_argument("binding extent/overflow refused");
 for(std::size_t i=0;i<regions.size();++i)for(std::size_t j=i+1;j<regions.size();++j){auto a=regions[i],b=regions[j];
  if((a.writable||b.writable)&&a.address<b.address+b.bytes&&b.address<a.address+a.bytes)
   throw std::invalid_argument("writable binding alias refused");
 }
}
}
