#pragma once
#include "performance.hpp"
namespace packet21 {
enum class InputTransform : unsigned { none, silu_div4, hc_mix };
enum class OutputTransform : unsigned { none, residual, silu_product, scale, hc_residual };
struct BatchSpec {
 integrated::Matrix matrix{}, peer{};
 unsigned variant=2,peer_variant=2;
 bool paired=false,shared_input=false;
 InputTransform input=InputTransform::none;
 ownrt::Allocation auxiliary=0,materialized_input=0;
 OutputTransform output=OutputTransform::none;
 // paired retains matrix.y + peer.y; activation is written to other.
 // residual reads other, writes destination; scale writes destination.
 ownrt::Allocation other=0,destination=0;
 float scale=1.f;
 ownrt::Allocation route_prob=0;unsigned route_top=0;
};
struct PreparedBatch {
 std::vector<uint8_t> descriptor_bytes;
 std::vector<ownrt::Allocation> bindings;
 std::vector<unsigned> binding_access;
 size_t groups=0;
 unsigned count=0,local_columns=1;
};
// Does not allocate, upload, wait or submit. Engine owns descriptor memory.
PreparedBatch prepare_batch(ownrt::Device&,const std::vector<BatchSpec>&,unsigned input_rows=1);
integrated::Launch gemv_batch(ownrt::Device&,const PreparedBatch&,ownrt::Allocation table);
}
