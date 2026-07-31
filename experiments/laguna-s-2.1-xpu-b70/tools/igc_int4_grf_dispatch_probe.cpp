// Instantiate the production generic BF16/INT4 w4a16_policy_m_8 launcher so
// its separately named 128- and 256-GRF command-group branches can be audited
// without compiling every grouped-GEMM policy in the extension.
#include <sycl/sycl.hpp>

#include "csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp"

using namespace cute;
using namespace MoE;

int main() {
  sycl::queue q{sycl::gpu_selector_v};
  constexpr int total_m = 120;
  constexpr int n = 64;
  constexpr int k = 256;
  constexpr int experts = 64;
  auto* a = sycl::malloc_device<bfloat16_t>(total_m * k, q);
  auto* b = sycl::malloc_device<uint8_t>(experts * n * k / 2, q);
  auto* scales = sycl::malloc_device<bfloat16_t>(experts * n * k / 32, q);
  auto* d = sycl::malloc_device<bfloat16_t>(total_m * n, q);
  auto* rows = sycl::malloc_device<int>(experts, q);
  auto* atomic = sycl::malloc_device<int32_t>(1, q);
  MoEGEMMLauncher<'R', 'C', w4a16_policy_m_8>(
      q,
      a,
      b,
      scales,
      static_cast<const bfloat16_t*>(nullptr),
      d,
      n,
      k,
      total_m,
      rows,
      experts,
      32,
      atomic);
  return 0;
}
