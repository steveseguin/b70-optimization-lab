// Matched static probe for ordinary vs tile-record INT4 K32xN64 loads.
#include <cstdio>
#include <sycl/sycl.hpp>

#include "csrc/xpu/grouped_gemm/xe_2/gemm_xe2_policy.hpp"
#include "csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2.hpp"

using namespace cute;
using namespace MoE;

template <bool TILE_RECORD>
class LagunaInt4TileRecordProbe;

template <bool TILE_RECORD, class policy>
void launch(
    sycl::queue& q,
    const bfloat16_t* A,
    const uint8_t* B,
    const bfloat16_t* S,
    bfloat16_t* D,
    int n,
    int k) {
  auto op = XE_DPAS_TT<8, float, bfloat16_t>{};
  using WGTile = typename policy::WGTile;
  using SGLayout = typename policy::SGLayout;
  using MMA = typename TiledMMAHelper<
      MMA_Atom<decltype(op)>,
      Layout<WGTile>,
      SGLayout>::TiledMMA;
  auto mma = MMA{};
  using GmemTiledCopyA = typename policy::GmemTiledCopyA;
  using GmemTiledCopyB = typename policy::GmemTiledCopyB;
  using GmemTiledCopyD = typename policy::GmemTiledCopyD;

  sycl::range<3> local(1, 1, size(mma));
  sycl::range<3> global(1, 8, 1);
  namespace syclex = sycl::ext::oneapi::experimental;
  namespace intelex = sycl::ext::intel::experimental;
  q.submit([&](sycl::handler& cgh) {
     syclex::properties props{
         syclex::sub_group_size<16>, intelex::grf_size<128>};
     cgh.parallel_for<LagunaInt4TileRecordProbe<TILE_RECORD>>(
         sycl::nd_range<3>(global * local, local),
         props,
         [=](sycl::nd_item<3>) {
           auto A_tensor = make_moe_tensor<bfloat16_t, 'R'>(
               const_cast<bfloat16_t*>(A), 8, k);
           auto B_tensor = make_moe_tensor<int4_t, 'R'>(
               reinterpret_cast<int4_t*>(const_cast<uint8_t*>(B)), n, k);
           auto D_tensor = make_moe_tensor<bfloat16_t, 'R'>(D, 8, n);
           auto tile_coord = make_coord(0, 0, _, 0);
           xe_gemm_4bits<
               GmemTiledCopyA,
               GmemTiledCopyB,
               GmemTiledCopyD,
               32,
               TILE_RECORD,
               false,
               true,
               false,
               !TILE_RECORD>(
               A_tensor,
               B_tensor,
               S,
               static_cast<const bfloat16_t*>(nullptr),
               D_tensor,
               tile_coord,
               mma,
               TILE_RECORD ? B : nullptr);
         });
   }).wait();
}

int main() {
  sycl::queue q{sycl::gpu_selector_v};
  int n = 64;
  int k = 256;
  auto* A = sycl::malloc_device<bfloat16_t>(8 * k, q);
  auto* B = sycl::malloc_device<uint8_t>(n * k / 2 + n * k / 32 * 2, q);
  auto* S = sycl::malloc_device<bfloat16_t>(n * k / 32, q);
  auto* D = sycl::malloc_device<bfloat16_t>(8 * n, q);
  launch<false, w4a16_policy_m_8>(q, A, B, S, D, n, k);
  launch<true, w4a16_policy_m_8>(q, A, B, S, D, n, k);
  ::printf("ok\n");
  return 0;
}
