// Inactive CPU-only dispatcher prototype. No new numerical formulas/kernels.
#include <ATen/core/Tensor.h>
#include <ATen/ops/rms_norm.h>
#include <ATen/ops/sigmoid.h>
#include <ATen/ops/gelu.h>
#include <torch/library.h>
#include <cmath>
#include <limits>
#include <optional>
#include <vector>

namespace {
void check_result(const at::Tensor& input, const at::Tensor& result) {
  std::vector<int64_t> strides(input.dim());
  int64_t stride = 1;
  for (int64_t i = input.dim(); i-- > 0;) {
    strides[i] = stride;
    const int64_t size = std::max<int64_t>(input.size(i), 1);
    TORCH_CHECK(stride <= std::numeric_limits<int64_t>::max() / size,
                "Native result canonical stride overflow");
    stride *= size;
  }
  TORCH_CHECK(result.sizes() == input.sizes() && result.scalar_type() == input.scalar_type()
      && result.device() == input.device() && result.strides().equals(strides),
      "Native result violates the reviewed fake layout");
  TORCH_CHECK(!result.is_alias_of(input), "Native result aliases input");
}

void activation_layout(const at::Tensor& input) {
  TORCH_CHECK((input.scalar_type() == at::kBFloat16 || input.scalar_type() == at::kFloat)
      && input.is_contiguous(), "Native activations require static contiguous BF16/F32 input");
  for (auto size : input.sizes()) {
    TORCH_CHECK(size >= 0, "Native activations require nonnegative static dimensions");
  }
}

at::Tensor native_rms(const at::Tensor& input, at::IntArrayRef normalized_shape,
                      const std::optional<at::Tensor>& weight, std::optional<double> eps) {
  TORCH_CHECK(!eps || (std::isfinite(*eps) && *eps >= 0),
              "Native RMS candidate requires finite nonnegative epsilon or None");
  TORCH_CHECK(input.is_contiguous(), "Native RMS candidate requires contiguous input");
  TORCH_CHECK(!normalized_shape.empty() && normalized_shape.size() <= static_cast<size_t>(input.dim()),
              "Native RMS candidate requires a static matching normalization shape");
  const auto offset = input.dim() - static_cast<int64_t>(normalized_shape.size());
  for (size_t i = 0; i < normalized_shape.size(); ++i) {
    TORCH_CHECK(normalized_shape[i] > 0 && input.size(offset + i) == normalized_shape[i],
                "Native RMS candidate requires a static matching normalization shape");
  }
  if (weight) {
    TORCH_CHECK(weight->is_contiguous() && weight->sizes().equals(normalized_shape)
        && weight->scalar_type() == input.scalar_type() && weight->device() == input.device(),
        "Native RMS candidate requires matching contiguous weight");
  }
  auto result = at::rms_norm(input, normalized_shape, weight, eps);
  check_result(input, result);
  TORCH_CHECK(!weight || !result.is_alias_of(*weight), "Native RMS result aliases weight");
  return result;
}

at::Tensor native_sigmoid(const at::Tensor& input) {
  activation_layout(input);
  auto result = at::sigmoid(input);
  check_result(input, result);
  return result;
}

at::Tensor native_gelu(const at::Tensor& input, c10::string_view approximate) {
  activation_layout(input);
  TORCH_CHECK(approximate == "tanh", "Only explicit tanh GELU is supported");
  auto result = at::gelu(input, approximate);
  check_result(input, result);
  return result;
}
}  // namespace

TORCH_LIBRARY(ltx_exact_cpp_cpu01, m) {
  m.def("rms(Tensor input, int[] normalized_shape, Tensor? weight, float? eps) -> Tensor");
  m.def("sigmoid(Tensor input) -> Tensor");
  m.def("gelu(Tensor input, str approximate) -> Tensor");
}
TORCH_LIBRARY_IMPL(ltx_exact_cpp_cpu01, CPU, m) {
  m.impl("rms", TORCH_FN(native_rms));
  m.impl("sigmoid", TORCH_FN(native_sigmoid));
  m.impl("gelu", TORCH_FN(native_gelu));
}
