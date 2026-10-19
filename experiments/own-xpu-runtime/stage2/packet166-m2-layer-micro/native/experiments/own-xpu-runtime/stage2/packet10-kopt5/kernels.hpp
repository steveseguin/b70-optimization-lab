#pragma once
#include "expanded.hpp"
#include "../packet9-kopt4/kernels.hpp"
namespace iq3::expanded {
ownrt::Event dequant(ownrt::Device&,Type,ownrt::Allocation,ownrt::Allocation,unsigned rows,unsigned k);
// Dense only: experts retain the qualified packed fused packet9 path.
kopt3::Launch gemv(ownrt::Device&,const kopt3::Matrix&,unsigned split);
inline unsigned dispatch_split(Type t,unsigned rows,unsigned k) {
 unsigned v=kopt4::dispatch_variant(unsigned(t),rows,k,1);
 return v==1 || v==4?4:1;
}
}
