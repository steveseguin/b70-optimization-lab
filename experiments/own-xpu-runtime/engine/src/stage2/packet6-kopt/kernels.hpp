#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet2/kernels/device.hpp"
namespace iq3::kopt {
struct Matrix {
  Type type;ownrt::Allocation w,x,y;size_t rows,columns;
  Type activation=Type::BF16,output_type=Type::BF16;
  ownrt::Allocation fp32=0;
};
ownrt::Event gemv(ownrt::Device&,Type,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,size_t,size_t,
                  Type=Type::BF16,Type=Type::BF16,unsigned=16,ownrt::Allocation=0);
ownrt::Event routed_gemv(ownrt::Device&,Type,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,
                         ownrt::Allocation,ownrt::Allocation,uint32_t,uint32_t,size_t,uint32_t,uint32_t,
                         Type=Type::BF16,Type=Type::BF16,unsigned=16,ownrt::Allocation=0);
// Dense matrix applied to `tokens` independent rows (x [tokens][k], y [tokens][rows]); per-row arithmetic unchanged.
ownrt::Event gemv_tokens(ownrt::Device&,Type,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,size_t,size_t,uint32_t,
                         Type=Type::BF16,Type=Type::BF16,unsigned=16);
// HC gate (rows = 4*width) plus its mix epilogue: also writes mix[width] from norm[4*width] (see kernels.cpp).
ownrt::Event gemv_mix(ownrt::Device&,Type,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,size_t,size_t,Type,Type,unsigned,
                      ownrt::Allocation,ownrt::Allocation,uint32_t);
// Tensor-parallel expert placement: mask the routes of experts another card owns; take those slots' rows from the peer.
ownrt::Event route_mask(ownrt::Device&,ownrt::Allocation,ownrt::Allocation,uint32_t,uint32_t,bool by_slot=false);
ownrt::Event slot_select(ownrt::Device&,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,uint32_t,uint32_t,uint32_t,bool by_slot=false);
// Compact slots (OWNRT_TP_EXPERTS=compact): routes/routes_down of slots parity, parity+2, ... into compact arrays.
ownrt::Event route_compact(ownrt::Device&,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,ownrt::Allocation,uint32_t top,uint32_t parity);
ownrt::Event slot_rows_compact(ownrt::Device&,ownrt::Allocation rows,ownrt::Allocation compact,uint32_t top,uint32_t parity,uint32_t words);
// OWNRT_PREFILL_EXPERT_PARITY (2026-10-30): n slots' routes / down routes, kept when expert_id % 2 == parity, else the skip route.
ownrt::Event route_parity(ownrt::Device&,ownrt::Allocation routes,ownrt::Allocation routes_down,ownrt::Allocation out,ownrt::Allocation out_down,uint32_t n,uint32_t parity);
ownrt::Event route_balance(ownrt::Device&,ownrt::Allocation routes,ownrt::Allocation routes_down,ownrt::Allocation out,ownrt::Allocation out_down,uint32_t n,uint32_t experts,uint32_t card); // OWNRT_PREFILL_EXPERT_BALANCE
// OWNRT_TP_EXPERT_PAIR (2026-10-30): gate and up routed rows of one layer plus act = silu(gate) * up in one launch.
bool routed_pairs(Type,size_t k,uint32_t count,Type a,Type o,unsigned sg,ownrt::Allocation fp32);
ownrt::Event routed_pair(ownrt::Device&,Type,ownrt::Allocation w,ownrt::Allocation wu,ownrt::Allocation x,ownrt::Allocation y,ownrt::Allocation yu,
                         ownrt::Allocation routes,ownrt::Allocation status,ownrt::Allocation su,uint32_t experts,uint32_t rows,size_t k,uint32_t count,
                         uint32_t span,ownrt::Allocation act,ownrt::Allocation active,ownrt::Allocation error,ownrt::Allocation position,int limit);
// Independent inputs only: this does not fuse across real activation dependencies.
ownrt::Event fused_gemv(ownrt::Device&,const std::vector<Matrix>&,unsigned=16);
// Populated only inside a coordinator-authorized submit; never enumerates.
std::string device_properties();
}
