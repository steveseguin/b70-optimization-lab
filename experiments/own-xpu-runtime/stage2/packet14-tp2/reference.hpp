#pragma once
#include "../packet13-integrate/arithmetic.hpp"
#include "../packet10-kopt5/expanded.hpp"
namespace tp2 {
inline constexpr char version[]="iq3-p14-full-row-p13-tree-slot-order-v1";
inline std::pair<size_t,size_t> rows(size_t n,int rank) {
  if(n<2 || rank<0 || rank>1)throw std::invalid_argument("row partition");
  return {rank?n/2:0,rank?n:n/2};
}
inline int expert_owner(unsigned id,unsigned experts=512) {
  if(experts%2 || id>=experts)throw std::invalid_argument("expert id");
  return id>=experts/2;
}
// Do NOT substitute sum(A slots)+sum(B slots): this preserves packet13's
// serial FP32 multiply/add at each original route slot and BF16 boundary.
inline float ordered_slots(const uint16_t* down,const float* prob,unsigned h,unsigned row,unsigned slots) {
  float sum=0;
  for(unsigned j=0;j<slots;++j){float product=iq3::bits_float(uint32_t(down[j*h+row])<<16)*prob[j];sum=sum+product;}
  return sum;
}
inline float candidate_ab(float a,float b){return a+b;} // rejected as expert replacement
}
