#include <ATen/xpu/XPUGraph.h>
#include <c10/xpu/XPUStream.h>
#include <torch/extension.h>

#include <cstdint>
#include <stdexcept>

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
}
