#pragma once
#include "../packet8-kopt3/reference.hpp"
namespace iq3::kopt4 {
// Four subgroups cooperate on one row. The local tree is EXACTLY packet7/8
// contiguous tile split4, not an atomic or unspecified SYCL reduction.
inline float row(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t k,unsigned split) {
 if(split!=1 && split!=4)throw std::invalid_argument("split must be 1 or 4");
 return kopt3::row(t,w,x,a,k,split==4?kopt3::Variant::constant_split4:kopt3::Variant::constant);
}
inline size_t work_groups(unsigned rows,unsigned count,unsigned split,unsigned matrices=1) {
 if(!rows || !count || (split!=1 && split!=4))throw std::invalid_argument("geometry");
 return size_t(count)*((size_t(rows)*split+3)/4)*matrices;
}
// Packet3 contract: round each down row BF16, then weight and accumulate
// slots 0..9 in their DEVICE route order, then round the mixture once.
inline float combine(const uint16_t* down,const float* weights,unsigned rows,unsigned r) {
 float sum=0;
 for(unsigned slot=0;slot<10;++slot) {
   float v=bits_float(uint32_t(down[size_t(slot)*rows+r])<<16);
   float product=v*weights[slot];sum=sum+product;
 }
 return sum;
}
}
