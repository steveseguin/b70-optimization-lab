#include <ATen/xpu/XPUGraph.h>
#include <c10/xpu/XPUStream.h>
#include <level_zero/layers/zel_tracing_api.h>
#include <level_zero/layers/zel_tracing_register_cb.h>
#include <level_zero/ze_api.h>
#include <sycl/backend.hpp>
#include <torch/extension.h>

#include <cstdint>
#include <stdexcept>
#include <string>
#include <tuple>
#include <variant>

namespace {

void replay_current_queue(std::uint64_t executable_address) {
  if (executable_address == 0) {
    throw std::invalid_argument("null XPU command-graph executable");
  }
  auto* executable = reinterpret_cast<at::xpu::xpuGraphExec_t*>(
      static_cast<std::uintptr_t>(executable_address));
  auto& queue = c10::xpu::getCurrentXPUStream().queue();
  queue.ext_oneapi_graph(*executable);
}

void check_ze(ze_result_t result, const char* operation) {
  if (result != ZE_RESULT_SUCCESS) {
    throw std::runtime_error(
        std::string(operation) + " failed with ze_result_t=" +
        std::to_string(static_cast<unsigned int>(result)));
  }
}

struct GraphListHarvest {
  ze_command_list_handle_t expected_immediate = nullptr;
  ze_command_list_handle_t regular = nullptr;
  std::uint32_t matching_appends = 0;
};

void ZE_APICALL capture_immediate_append(
    ze_command_list_immediate_append_command_lists_exp_params_t* params,
    ze_result_t result,
    void* tracer_user_data,
    void**) {
  auto* harvest = static_cast<GraphListHarvest*>(tracer_user_data);
  if (result != ZE_RESULT_SUCCESS || params == nullptr ||
      params->phCommandListImmediate == nullptr ||
      params->pnumCommandLists == nullptr ||
      params->pphCommandLists == nullptr ||
      *params->pphCommandLists == nullptr) {
    return;
  }
  if (*params->phCommandListImmediate != harvest->expected_immediate ||
      *params->pnumCommandLists != 1) {
    return;
  }
  harvest->regular = (*params->pphCommandLists)[0];
  ++harvest->matching_appends;
}

std::tuple<std::uint64_t, std::uint64_t, std::uint32_t>
harvest_raw_level_zero_handles(
    std::uint64_t executable_address) {
  if (executable_address == 0) {
    throw std::invalid_argument("null XPU command-graph executable");
  }
  auto* executable = reinterpret_cast<at::xpu::xpuGraphExec_t*>(
      static_cast<std::uintptr_t>(executable_address));
  auto& queue = c10::xpu::getCurrentXPUStream().queue();
  if (!queue.is_in_order()) {
    throw std::runtime_error(
        "raw Level Zero replay requires PyTorch's current queue to be in-order");
  }
  auto queue_native =
      sycl::get_native<sycl::backend::ext_oneapi_level_zero>(queue);
  auto* immediate_command_list =
      std::get_if<ze_command_list_handle_t>(&queue_native);
  if (immediate_command_list == nullptr || *immediate_command_list == nullptr) {
    throw std::runtime_error(
        "the current PyTorch SYCL queue is not backed by an owned Level Zero "
        "immediate command list");
  }
  GraphListHarvest harvest;
  harvest.expected_immediate = *immediate_command_list;
  zel_tracer_desc_t tracer_desc{
      ZEL_STRUCTURE_TYPE_TRACER_DESC, nullptr, &harvest};
  zel_tracer_handle_t tracer = nullptr;
  check_ze(zelTracerCreate(&tracer_desc, &tracer), "zelTracerCreate");
  try {
    check_ze(
        zelTracerCommandListImmediateAppendCommandListsExpRegisterCallback(
            tracer, ZEL_REGISTER_EPILOGUE, capture_immediate_append),
        "zelTracerCommandListImmediateAppendCommandListsExpRegisterCallback");
    check_ze(zelTracerSetEnabled(tracer, true), "zelTracerSetEnabled(true)");
    queue.ext_oneapi_graph(*executable);
    check_ze(zelTracerSetEnabled(tracer, false), "zelTracerSetEnabled(false)");
    check_ze(zelTracerDestroy(tracer), "zelTracerDestroy");
    tracer = nullptr;
  } catch (...) {
    if (tracer != nullptr) {
      zelTracerSetEnabled(tracer, false);
      zelTracerDestroy(tracer);
    }
    throw;
  }
  if (harvest.matching_appends != 1 || harvest.regular == nullptr) {
    throw std::runtime_error(
        "failed to harvest exactly one regular Level Zero command list from "
        "the sacrificial SYCL graph replay");
  }
  return {
      static_cast<std::uint64_t>(reinterpret_cast<std::uintptr_t>(
          *immediate_command_list)),
      static_cast<std::uint64_t>(
          reinterpret_cast<std::uintptr_t>(harvest.regular)),
      harvest.matching_appends};
}

void replay_raw_level_zero(
    std::uint64_t immediate_command_list_address,
    std::uint64_t regular_command_list_address) {
  if (immediate_command_list_address == 0 ||
      regular_command_list_address == 0) {
    throw std::invalid_argument("null raw Level Zero command-list handle");
  }

  auto& queue = c10::xpu::getCurrentXPUStream().queue();
  if (!queue.is_in_order()) {
    throw std::runtime_error(
        "raw Level Zero replay requires PyTorch's current queue to be in-order");
  }
  auto queue_native =
      sycl::get_native<sycl::backend::ext_oneapi_level_zero>(queue);
  auto* current_immediate =
      std::get_if<ze_command_list_handle_t>(&queue_native);
  if (current_immediate == nullptr || *current_immediate == nullptr) {
    throw std::runtime_error(
        "the current PyTorch SYCL queue is no longer an immediate command list");
  }
  auto expected_immediate = reinterpret_cast<ze_command_list_handle_t>(
      static_cast<std::uintptr_t>(immediate_command_list_address));
  if (*current_immediate != expected_immediate) {
    throw std::runtime_error(
        "the current PyTorch Level Zero immediate command list changed");
  }
  auto regular_command_list = reinterpret_cast<ze_command_list_handle_t>(
      static_cast<std::uintptr_t>(regular_command_list_address));
  check_ze(
      zeCommandListImmediateAppendCommandListsExp(
          *current_immediate,
          1,
          &regular_command_list,
          nullptr,
          0,
          nullptr),
      "zeCommandListImmediateAppendCommandListsExp");
}

std::uint64_t current_queue_object_address() {
  auto& queue = c10::xpu::getCurrentXPUStream().queue();
  return static_cast<std::uint64_t>(reinterpret_cast<std::uintptr_t>(&queue));
}

}  // namespace

PYBIND11_MODULE(TORCH_EXTENSION_NAME, module) {
  module.def(
      "replay_current_queue",
      &replay_current_queue,
      "Append an owned executable SYCL command graph to the current XPU queue");
  module.def(
      "current_queue_object_address",
      &current_queue_object_address,
      "Return the address of the current PyTorch SYCL queue object");
  module.def(
      "harvest_raw_level_zero_handles",
      &harvest_raw_level_zero_handles,
      "Borrow raw lists from one sacrificial traced SYCL graph replay");
  module.def(
      "replay_raw_level_zero",
      &replay_raw_level_zero,
      "Append a regular graph list directly to PyTorch's owned immediate list");
}
