#include <sycl/sycl.hpp>
#include <torch/all.h>
#include <torch/library.h>
#include <c10/xpu/XPUStream.h>
#include "dispatch_utils.h"
#include "causal_conv1d.hpp"
#include "gated_delta_rule.hpp"
namespace vllm { namespace xpu {
static inline sycl::queue& vllmGetQueue(at::DeviceIndex device_index = -1) {
  auto current_stream = c10::xpu::getCurrentXPUStream(device_index);
  auto& queue = current_stream.queue();
  return queue;
}
}}
std::vector<torch::Tensor> causal_conv1d_spec(
    torch::Tensor& z,  // [num_actual_tokens, num_v_heads / tp_size, head_v_dim]
    const torch::Tensor& projected_states_qkvz,
    const torch::Tensor& projected_states_ba,
    const int64_t num_k_heads,
    const int64_t num_v_heads,
    const int64_t head_k_dim,
    const int64_t head_v_dim,
    torch::Tensor& conv_state,
    const torch::Tensor& conv_weights,
    const std::optional<torch::Tensor>& conv_bias,
    const std::string& activation,
    const int64_t num_prefills,
    const int64_t num_decodes,
    const int64_t num_spec_decodes,
    const torch::Tensor& spec_query_start_loc,
    const torch::Tensor& spec_token_indx,
    const torch::Tensor& spec_state_indices_tensor,
    const torch::Tensor& num_accepted_tokens,
    const int64_t num_actual_tokens,
    const int64_t tp_size,
    const bool reorder_input) {
  TORCH_CHECK(z.is_contiguous(), "z must be contiguous");
  TORCH_CHECK(
      projected_states_qkvz.is_contiguous(),
      "projected_states_qkvz must be contiguous");
  TORCH_CHECK(
      projected_states_ba.is_contiguous(),
      "projected_states_ba must be contiguous");
  TORCH_CHECK(
      conv_state[0].is_contiguous(),
      "conv_state of each batch must be contiguous");
  TORCH_CHECK(conv_weights.is_contiguous(), "conv_weights must be contiguous");

  TORCH_CHECK(
      num_spec_decodes > 0, "causal_conv1d_spec requires num_spec_decodes > 0");

  TORCH_CHECK(
      spec_query_start_loc.is_contiguous(),
      "spec_query_start_loc must be contiguous");
  TORCH_CHECK(
      spec_query_start_loc.dtype() == torch::kInt32,
      "spec_query_start_loc must be of int32 dtype");
  TORCH_CHECK(
      spec_query_start_loc.dim() == 1,
      "spec_query_start_loc must be 1D of shape [num_spec_decodes + 1]");
  TORCH_CHECK(
      spec_query_start_loc.size(0) == num_spec_decodes + 1,
      "spec_query_start_loc must have size [num_spec_decodes + 1]");

  TORCH_CHECK(
      spec_token_indx.is_contiguous(), "spec_token_indx must be contiguous");
  TORCH_CHECK(
      spec_token_indx.dtype() == torch::kInt32,
      "spec_token_indx must be of int32 dtype");
  TORCH_CHECK(
      spec_token_indx.dim() == 1,
      "spec_token_indx must be 1D of shape [spec_token]");
  const int spec_token = spec_token_indx.size(0);

  TORCH_CHECK(
      spec_state_indices_tensor.is_contiguous(),
      "spec_state_indices_tensor must be contiguous");
  TORCH_CHECK(
      spec_state_indices_tensor.dtype() == torch::kInt32,
      "spec_state_indices_tensor must be of int32 dtype");
  TORCH_CHECK(
      spec_state_indices_tensor.dim() == 2,
      "spec_state_indices_tensor must be 2D of shape [num_spec_decodes, "
      "num_speculative_tokens + 1]");
  TORCH_CHECK(
      spec_state_indices_tensor.size(0) == num_spec_decodes,
      "spec_state_indices_tensor must have size [num_spec_decodes, "
      "num_speculative_tokens + 1]");
  const int num_speculative_tokens = spec_state_indices_tensor.size(1) - 1;
  const int64_t required_conv_state_len =
      conv_weights.size(1) - 1 + num_speculative_tokens;
  TORCH_CHECK(
      conv_state.size(1) >= required_conv_state_len,
      "conv_state must have at least ",
      required_conv_state_len,
      " rows for speculative decoding, but got ",
      conv_state.size(1));

  TORCH_CHECK(
      num_accepted_tokens.is_contiguous(),
      "num_accepted_tokens must be contiguous");
  TORCH_CHECK(
      num_accepted_tokens.dtype() == torch::kInt32,
      "num_accepted_tokens must be of int32 dtype");
  TORCH_CHECK(
      num_accepted_tokens.dim() == 1,
      "num_accepted_tokens must be 1D of shape [num_spec_decodes]");
  TORCH_CHECK(
      num_accepted_tokens.size(0) == num_spec_decodes,
      "num_accepted_tokens size must be num_spec_decodes");

  TORCH_CHECK(spec_token == num_spec_decodes * (num_speculative_tokens + 1));
  TORCH_CHECK(spec_token > 0, "spec_token must be > 0 for causal_conv1d_spec");

  TORCH_CHECK(
      z.size(0) >= num_actual_tokens,
      "z.size(0) (",
      z.size(0),
      ") must be >= num_actual_tokens (",
      num_actual_tokens,
      ")");
  TORCH_CHECK(z.size(1) == num_v_heads / tp_size);
  TORCH_CHECK(z.size(2) == head_v_dim);

  TORCH_CHECK(
      projected_states_qkvz.size(0) >= num_actual_tokens,
      "projected_states_qkvz.size(0) (",
      projected_states_qkvz.size(0),
      ") must be >= num_actual_tokens (",
      num_actual_tokens,
      ")");
  TORCH_CHECK(
      projected_states_qkvz.size(1) ==
      num_k_heads / tp_size *
          (2 * head_k_dim + 2 * head_v_dim * num_v_heads / num_k_heads));

  TORCH_CHECK(
      projected_states_ba.size(0) >= num_actual_tokens,
      "projected_states_ba.size(0) (",
      projected_states_ba.size(0),
      ") must be >= num_actual_tokens (",
      num_actual_tokens,
      ")");
  TORCH_CHECK(projected_states_ba.size(1) == 2 * num_v_heads / tp_size);

  // Narrow the (possibly cudagraph-padded) leading dim to the active prefix so
  // the conv kernels never read or write padded rows.
  auto z_active = z.narrow(0, 0, num_actual_tokens);
  auto projected_states_qkvz_active =
      projected_states_qkvz.narrow(0, 0, num_actual_tokens);
  auto projected_states_ba_active =
      projected_states_ba.narrow(0, 0, num_actual_tokens);

  auto& queue = vllm::xpu::vllmGetQueue();
  auto dtype = projected_states_qkvz.dtype();
  auto device = projected_states_qkvz.device();
  gdn::ActMode act_mode;

  if (activation == "silu") {
    act_mode = gdn::ActMode::silu;
  } else if (activation == "swish") {
    act_mode = gdn::ActMode::swish;
  } else {
    TORCH_CHECK(false);
  }
  const int pad_slot_id = -1;

  std::optional<torch::Tensor> empty_tensor{std::nullopt};

  torch::Tensor q = torch::empty(
      {spec_token, num_k_heads / tp_size, head_k_dim},
      torch::dtype(dtype).device(device).requires_grad(false));
  torch::Tensor k = torch::empty(
      {spec_token, num_k_heads / tp_size, head_k_dim},
      torch::dtype(dtype).device(device).requires_grad(false));
  torch::Tensor v = torch::empty(
      {spec_token, num_v_heads / tp_size, head_v_dim},
      torch::dtype(dtype).device(device).requires_grad(false));
  torch::Tensor b = torch::empty(
      {spec_token, num_v_heads / tp_size},
      torch::dtype(dtype).device(device).requires_grad(false));
  torch::Tensor a = torch::empty(
      {spec_token, num_v_heads / tp_size},
      torch::dtype(dtype).device(device).requires_grad(false));

  gdn::causal_conv1d(
      queue,
      q,
      k,
      v,
      z_active,
      b,
      a,
      projected_states_qkvz_active,
      projected_states_ba_active,
      conv_weights,
      conv_bias,
      conv_state,
      spec_query_start_loc,
      spec_token_indx,
      spec_state_indices_tensor,
      empty_tensor,
      num_accepted_tokens,
      act_mode,
      pad_slot_id,
      num_prefills,
      num_decodes,
      num_spec_decodes,
      reorder_input);

  return {q, k, v, b, a};
}
void gated_delta_rule_spec(
    torch::Tensor& core_attn_out,  // [num_actual_tokens, num_v_heads / tp_size,
                                   // head_v_dim]
    const torch::Tensor& q,
    const torch::Tensor& k,
    const torch::Tensor& v,
    const torch::Tensor& b,
    const torch::Tensor& a,
    const int64_t num_v_heads,
    const int64_t head_v_dim,
    const torch::Tensor& A_log,
    const torch::Tensor& dt_bias,
    torch::Tensor& ssm_state,
    const int64_t num_prefills,
    const int64_t num_decodes,
    const int64_t num_spec_decodes,
    const torch::Tensor& spec_query_start_loc,
    const torch::Tensor& spec_token_indx,
    const torch::Tensor& spec_state_indices_tensor,
    const torch::Tensor& num_accepted_tokens,
    const int64_t num_actual_tokens,
    const int64_t tp_size) {
  TORCH_CHECK(
      core_attn_out.is_contiguous(), "core_attn_out must be contiguous");
  TORCH_CHECK(
      ssm_state[0].is_contiguous(),
      "ssm_state of each batch must be contiguous");
  TORCH_CHECK(A_log.is_contiguous(), "A_log must be contiguous");
  TORCH_CHECK(dt_bias.is_contiguous(), "dt_bias must be contiguous");

  TORCH_CHECK(
      core_attn_out.size(0) >= num_actual_tokens,
      "core_attn_out.size(0) (",
      core_attn_out.size(0),
      ") must be >= num_actual_tokens (",
      num_actual_tokens,
      ")");
  TORCH_CHECK(core_attn_out.size(1) == num_v_heads / tp_size);
  TORCH_CHECK(core_attn_out.size(2) == head_v_dim);

  TORCH_CHECK(
      num_spec_decodes > 0,
      "gated_delta_rule_spec requires num_spec_decodes > 0");

  // spec_token may be < num_actual_tokens when a spec-decode group coexists
  // with a non-spec group in the same batch: each delta op processes only its
  // own tokens (located via spec_token_indx) while writing into the shared
  // core_attn_out. Requiring spec_token == num_actual_tokens would wrongly
  // reject that mixed case, so we only require it to be positive.
  const int spec_token = spec_token_indx.size(0);
  TORCH_CHECK(
      spec_token > 0, "spec_token must be > 0 for gated_delta_rule_spec");

  // Narrow the (possibly cudagraph-padded) leading dim to the active prefix.
  auto core_attn_out_active = core_attn_out.narrow(0, 0, num_actual_tokens);

  auto& queue = vllm::xpu::vllmGetQueue();
  std::optional<torch::Tensor> empty_tensor{std::nullopt};

  gdn::gated_delta_rule(
      queue,
      core_attn_out_active,
      q,
      k,
      v,
      b,
      a,
      A_log,
      dt_bias,
      ssm_state,
      spec_query_start_loc,
      spec_token_indx,
      spec_state_indices_tensor,
      empty_tensor,
      num_accepted_tokens,
      num_prefills,
      num_decodes,
      num_spec_decodes);
}
TORCH_LIBRARY(width_review, m) {
 m.def("conv", TORCH_FN(causal_conv1d_spec));
 m.def("delta", TORCH_FN(gated_delta_rule_spec));
}
