// Minimal code-generation probe for retaining Laguna INT4 scales in BF16.
#include <cstdio>
#include <sycl/sycl.hpp>

#include "csrc/xpu/grouped_gemm/xe_2/gemm_xe2_policy.hpp"
#include "csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.hpp"

using namespace cute;
using namespace MoE;

template <bool BF16_SCALE>
class LagunaInt4Bf16ScaleProbe;

template <bool BF16_SCALE, class Policy>
void launch(
    sycl::queue& q,
    const bfloat16_t* a,
    const uint8_t* b,
    const bfloat16_t* scales,
    bfloat16_t* d,
    int n,
    int k) {
  auto op = XE_DPAS_TT<8, float, bfloat16_t>{};
  using WGTile = typename Policy::WGTile;
  using SGLayout = typename Policy::SGLayout;
  using MMA = typename TiledMMAHelper<
      MMA_Atom<decltype(op)>, Layout<WGTile>, SGLayout>::TiledMMA;
  auto mma = MMA{};
  using GmemTiledCopyA = typename Policy::GmemTiledCopyA;
  using GmemTiledCopyB = typename Policy::GmemTiledCopyB;
  using GmemTiledCopyD = typename Policy::GmemTiledCopyD;

  sycl::range<3> local(1, 1, size(mma));
  sycl::range<3> global(1, 8, 1);
  q.parallel_for<LagunaInt4Bf16ScaleProbe<BF16_SCALE>>(
       sycl::nd_range<3>(global * local, local),
       [=](sycl::nd_item<3>) [[sycl::reqd_sub_group_size(16)]] {
         auto a_tensor = make_moe_tensor<bfloat16_t, 'R'>(
             const_cast<bfloat16_t*>(a), 8, k);
         auto b_tensor = make_moe_tensor<int4_t, 'R'>(
             reinterpret_cast<int4_t*>(const_cast<uint8_t*>(b)), n, k);
         auto d_tensor = make_moe_tensor<bfloat16_t, 'R'>(d, 8, n);
         auto tile_coord = make_coord(0, 0, _, 0);
         xe_gemm_4bits<
             GmemTiledCopyA,
             GmemTiledCopyB,
             GmemTiledCopyD,
             32,
             false,
             false,
             true,
             false,
             true,
             BF16_SCALE>(
             a_tensor,
             b_tensor,
             scales,
             static_cast<const bfloat16_t*>(nullptr),
             d_tensor,
             tile_coord,
             mma);
       })
      .wait();
}

int main() {
  sycl::queue q{sycl::gpu_selector_v};
  constexpr int n = 64;
  constexpr int k = 256;
  auto* a = sycl::malloc_device<bfloat16_t>(8 * k, q);
  auto* b = sycl::malloc_device<uint8_t>(n * k / 2, q);
  auto* scales = sycl::malloc_device<bfloat16_t>(n * k / 32, q);
  auto* d = sycl::malloc_device<bfloat16_t>(8 * n, q);
  launch<false, w4a16_policy_m_8>(q, a, b, scales, d, n, k);
  launch<true, w4a16_policy_m_8>(q, a, b, scales, d, n, k);
  printf("ok\n");
  return 0;
}
