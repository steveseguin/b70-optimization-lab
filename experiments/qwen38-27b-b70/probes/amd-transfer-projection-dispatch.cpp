// Source-only experiment: combine host dispatch, never quantize or merge BA.
// Baseline operations copied structurally from R304 qwen_gdn_linear_attn.py
// _deterministic_xpu_ba_prefill and utils.py _xpu_fp16_linear_rowchunk_impl.
#include <ATen/ATen.h>
#include <ATen/core/dispatch/Dispatcher.h>
#include <torch/library.h>
#include <algorithm>
#include <optional>
#include <tuple>
#include <vector>

using Tensor = at::Tensor;
using MaybeTensor = std::optional<Tensor>;

std::tuple<Tensor, Tensor> projection_pair(
    const Tensor& x, const Tensor& qkvz_kn, const Tensor& scales_kn,
    const Tensor& ba_nk) {
  TORCH_CHECK(x.device().type() == c10::DeviceType::XPU,
              "This diagnostic supports XPU only");
  TORCH_CHECK(x.dim() == 2 && x.size(0) > 0 && x.size(1) == 5120 &&
              x.scalar_type() == at::kHalf, "Expected FP16 [M,5120]");
  TORCH_CHECK(qkvz_kn.dim() == 2 && qkvz_kn.size(0) == 5120 &&
              qkvz_kn.size(1) == 8192 && qkvz_kn.stride(0) == 1 &&
              qkvz_kn.stride(1) == 5120 &&
              qkvz_kn.scalar_type() == at::ScalarType::Float8_e4m3fn,
              "Expected production FP8 QKVZ NT view [5120,8192]");
  TORCH_CHECK(ba_nk.sizes() == at::IntArrayRef({48,5120}) &&
              ba_nk.scalar_type() == at::kHalf && ba_nk.is_contiguous(),
              "Expected TP2 FP16 BA [48,5120]");
  TORCH_CHECK(scales_kn.sizes() == at::IntArrayRef({40,64}) &&
              scales_kn.scalar_type() == at::kFloat && scales_kn.is_contiguous(),
              "Expected FP32 scales [40,64]");
  TORCH_CHECK(x.device() == qkvz_kn.device() && x.device() == ba_nk.device() &&
              x.device() == scales_kn.device(), "All tensors must share device");
  static auto fp8 = c10::Dispatcher::singleton()
      .findSchemaOrThrow("_xpu_C::fp8_gemm_w8a16", "")
      .typed<Tensor(const Tensor&, const Tensor&, const MaybeTensor&, const MaybeTensor&)>();
  // Original native FP8 entry point: same physical weights, scales and output.
  auto qkvz = fp8.call(x, qkvz_kn, MaybeTensor(scales_kn), std::nullopt);
  Tensor ba;
  if (x.size(0) < 17) {
    // R224 chunk32 takes this exact F.linear path at rows1..16.
    ba = at::linear(x, ba_nk, std::nullopt);
  } else {
    // Original registered BA prefill route: fixed256-row F.linear calls.
    std::vector<Tensor> pieces;
    for (int64_t start = 0; start < x.size(0); start += 256) {
      const int64_t count = std::min<int64_t>(256, x.size(0)-start);
      auto block = x.slice(0, start, start+count);
      if (count != 256) {
        auto padded = at::zeros({256, x.size(1)}, x.options());
        padded.slice(0, 0, count).copy_(block);
        block = padded;
      }
      pieces.push_back(at::linear(block, ba_nk, std::nullopt).slice(0, 0, count));
    }
    ba = pieces.size() == 1 ? pieces[0] : at::cat(pieces, 0);
  }
  return {qkvz, ba};
}

TORCH_LIBRARY(amd_transfer, m) {
  m.def("projection_pair(Tensor x, Tensor qkvz_kn, Tensor scales_kn, Tensor ba_nk) -> (Tensor, Tensor)");
}
TORCH_LIBRARY_IMPL(amd_transfer, XPU, m) {
  m.impl("projection_pair", TORCH_FN(projection_pair));
}
