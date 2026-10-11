#pragma once
#include "math.hpp"
#include "owner.hpp"
namespace iq3 {
// Bindings are Arena handles, never application pointers. All output extents
// must be disjoint; F32 dequant output, 16-bit activations and GEMV output.
ownrt::Event dequant(ownrt::Device&,Type,ownrt::Allocation packed,ownrt::Allocation output,
                     size_t elements,unsigned subgroup=16);
ownrt::Event gemv(ownrt::Device&,Type,ownrt::Allocation packed,ownrt::Allocation x,
                  ownrt::Allocation output,size_t rows,size_t columns,
                  Type activation=Type::BF16,Type output_type=Type::BF16,unsigned subgroup=16,
                  ownrt::Allocation diagnostic_fp32=0);
// routing is a device Allocation containing route_count Route objects.
// Output [route_count, row_span]; unused/invalid rows -> canonical NaN.
// status[route] = 0 valid, 1 invalid; invalid routes never access bank/x.
// x [route_count,columns], bank [experts,rows,columns]. No host routing read.
ownrt::Event routed_gemv(ownrt::Device&,Type,ownrt::Allocation bank,ownrt::Allocation x,
                         ownrt::Allocation output,ownrt::Allocation routing,ownrt::Allocation status,
                         uint32_t experts,uint32_t rows,size_t columns,uint32_t route_count,uint32_t row_span,
                         Type activation=Type::BF16,Type output_type=Type::BF16,unsigned subgroup=16,
                         ownrt::Allocation diagnostic_fp32=0);
}
