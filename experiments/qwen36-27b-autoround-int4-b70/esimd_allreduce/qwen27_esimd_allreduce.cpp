#include <level_zero/ze_api.h>
#include <sycl/ext/intel/esimd.hpp>
#include <sycl/ext/intel/experimental/esimd/memory.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <sycl/ext/oneapi/bfloat16.hpp>
#include <sycl/sycl.hpp>

#include <ATen/DeviceGuard.h>
#include <c10/xpu/XPUFunctions.h>
#include <c10/xpu/XPUStream.h>
#include <torch/extension.h>

#include <array>
#include <cstdint>
#include <iomanip>
#include <sstream>
#include <string>
#include <variant>
#include <vector>

#define CHECK_XPU(x) TORCH_CHECK((x).is_xpu(), #x " must be on XPU")
#define CHECK_CONTIGUOUS(x) \
  TORCH_CHECK((x).is_contiguous(), #x " must be contiguous")

namespace {

using bf16 = sycl::ext::oneapi::bfloat16;
namespace esimd = sycl::ext::intel::esimd;
namespace esimd_exp = sycl::ext::intel::experimental::esimd;

constexpr int kSimd = 32;
constexpr int kWorkgroup = 16;
constexpr uint32_t kSlmBytes = 8;

void check_ze(ze_result_t result, const char* what) {
  TORCH_CHECK(result == ZE_RESULT_SUCCESS, what, " failed with ze_result=", result);
}

std::string bytes_to_hex(const void* data, size_t size) {
  const auto* bytes = static_cast<const uint8_t*>(data);
  std::ostringstream os;
  os << std::hex << std::setfill('0');
  for (size_t i = 0; i < size; ++i) {
    os << std::setw(2) << static_cast<unsigned>(bytes[i]);
  }
  return os.str();
}

bool hex_to_bytes(const std::string& hex, void* out, size_t size) {
  if (hex.size() != size * 2) {
    return false;
  }
  auto* bytes = static_cast<uint8_t*>(out);
  for (size_t i = 0; i < size; ++i) {
    char buf[3] = {hex[i * 2], hex[i * 2 + 1], '\0'};
    char* end = nullptr;
    const unsigned long value = std::strtoul(buf, &end, 16);
    if (end == nullptr || *end != '\0' || value > 255) {
      return false;
    }
    bytes[i] = static_cast<uint8_t>(value);
  }
  return true;
}

ze_context_handle_t current_l0_context() {
  auto sycl_context = c10::xpu::get_device_context();
  return sycl::get_native<sycl::backend::ext_oneapi_level_zero>(sycl_context);
}

ze_device_handle_t l0_device_for_index(int64_t device_index) {
  c10::xpu::check_device_index(static_cast<int>(device_index));
  auto sycl_device = c10::xpu::get_raw_device(static_cast<int>(device_index));
  return sycl::get_native<sycl::backend::ext_oneapi_level_zero>(sycl_device);
}

class EsimdIpcPublishBf16Kernel;
class EsimdIpcProbeSequenceKernel;
class EsimdIpcReduceBf16Kernel;
class EsimdPeerReadI32Kernel;
class EsimdLocalWriteI32Kernel;

struct L0ScopedEvent {
  ze_event_pool_handle_t pool = nullptr;
  ze_event_handle_t event = nullptr;
  int64_t scope = 0;
};

std::array<L0ScopedEvent, 16> scoped_events;

struct L0IpcEvent {
  ze_event_pool_handle_t pool = nullptr;
  ze_event_handle_t event = nullptr;
};

std::array<L0IpcEvent, 16> local_ipc_events;
std::vector<L0IpcEvent> opened_ipc_events;

struct L0IpcEventPair {
  ze_event_pool_handle_t pool = nullptr;
  std::array<ze_event_handle_t, 2> events = {nullptr, nullptr};
};

std::array<L0IpcEventPair, 16> local_ipc_event_pairs;
std::vector<L0IpcEventPair> opened_ipc_event_pairs;
std::vector<std::array<ze_event_handle_t, 2>> external_counter_event_pairs;

std::string native_queue_kind(torch::Tensor tensor) {
  const at::DeviceGuard device_guard(tensor.device());
  CHECK_XPU(tensor);
  auto& queue =
      c10::xpu::getCurrentXPUStream(tensor.device().index()).queue();
  auto native =
      sycl::get_native<sycl::backend::ext_oneapi_level_zero>(queue);
  if (std::holds_alternative<ze_command_list_handle_t>(native)) {
    return "immediate_command_list";
  }
  return "command_queue";
}

ze_command_list_handle_t immediate_command_list(sycl::queue& queue) {
  auto native =
      sycl::get_native<sycl::backend::ext_oneapi_level_zero>(queue);
  auto* command_list = std::get_if<ze_command_list_handle_t>(&native);
  TORCH_CHECK(command_list != nullptr,
              "Level Zero memory-range barrier requires an immediate command "
              "list-backed SYCL queue");
  return *command_list;
}

ze_event_handle_t scoped_event_for_device(int64_t device_index,
                                          int64_t event_scope) {
  TORCH_CHECK(device_index >= 0 &&
                  device_index < static_cast<int64_t>(scoped_events.size()),
              "unsupported XPU device index ", device_index);
  auto& state = scoped_events[device_index];
  if (state.event != nullptr) {
    TORCH_CHECK(state.scope == event_scope,
                "Level Zero event scope cannot change after first use");
    return state.event;
  }

  ze_event_pool_desc_t pool_desc = {};
  pool_desc.stype = ZE_STRUCTURE_TYPE_EVENT_POOL_DESC;
  pool_desc.flags = 0;
  pool_desc.count = 1;
  auto device = l0_device_for_index(device_index);
  check_ze(zeEventPoolCreate(current_l0_context(),
                             &pool_desc,
                             1,
                             &device,
                             &state.pool),
           "zeEventPoolCreate");

  ze_event_desc_t event_desc = {};
  event_desc.stype = ZE_STRUCTURE_TYPE_EVENT_DESC;
  event_desc.index = 0;
  event_desc.signal = event_scope == 2 ? ZE_EVENT_SCOPE_FLAG_HOST
                                       : ZE_EVENT_SCOPE_FLAG_DEVICE;
  event_desc.wait = 0;
  check_ze(zeEventCreate(state.pool, &event_desc, &state.event),
           "zeEventCreate");
  state.scope = event_scope;
  return state.event;
}

ze_event_handle_t append_l0_memory_ranges_barrier(
    sycl::queue& queue,
    torch::Tensor local_payload,
    torch::Tensor local_sequence,
    int64_t event_scope) {
  auto command_list = immediate_command_list(queue);
  const size_t range_sizes[] = {
      static_cast<size_t>(local_payload.nbytes()),
      static_cast<size_t>(local_sequence.nbytes()),
  };
  const void* ranges[] = {
      local_payload.data_ptr(),
      local_sequence.data_ptr(),
  };
  ze_event_handle_t signal_event = nullptr;
  if (event_scope != 0) {
    signal_event =
        scoped_event_for_device(local_payload.device().index(), event_scope);
  }
  check_ze(zeCommandListAppendMemoryRangesBarrier(
               command_list,
               2,
               range_sizes,
               ranges,
               signal_event,
               0,
               nullptr),
           "zeCommandListAppendMemoryRangesBarrier");
  return signal_event;
}

void read_peer_i32(int64_t peer_ptr, torch::Tensor output) {
  const at::DeviceGuard device_guard(output.device());
  CHECK_XPU(output);
  CHECK_CONTIGUOUS(output);
  TORCH_CHECK(output.scalar_type() == torch::kInt32 && output.numel() == 1,
              "output must contain one XPU int32");
  TORCH_CHECK(peer_ptr != 0, "peer_ptr must be non-zero");
  auto* remote = reinterpret_cast<int32_t*>(static_cast<uintptr_t>(peer_ptr));
  auto* out = output.data_ptr<int32_t>();
  auto& queue = c10::xpu::getCurrentXPUStream(output.device().index()).queue();
  queue.submit([&](sycl::handler& cgh) {
    cgh.parallel_for<EsimdPeerReadI32Kernel>(
        sycl::range<1>(1), [=](sycl::id<1>) SYCL_ESIMD_KERNEL {
          esimd::fence<esimd::memory_kind::global,
                       esimd::fence_flush_op::none,
                       esimd::fence_scope::system_acquire>();
          auto value =
              esimd_exp::lsc_block_load<int32_t,
                                        1,
                                        esimd_exp::lsc_data_size::default_size,
                                        esimd_exp::cache_hint::uncached,
                                        esimd_exp::cache_hint::uncached>(remote);
          esimd_exp::lsc_block_store<int32_t,
                                     1,
                                     esimd_exp::lsc_data_size::default_size,
                                     esimd_exp::cache_hint::write_back,
                                     esimd_exp::cache_hint::write_back>(out,
                                                                        value);
        });
  });
}

void write_local_i32(torch::Tensor local, int64_t value, int64_t fence_mode) {
  const at::DeviceGuard device_guard(local.device());
  CHECK_XPU(local);
  CHECK_CONTIGUOUS(local);
  TORCH_CHECK(local.scalar_type() == torch::kInt32 && local.numel() == 1,
              "local must contain one XPU int32");
  TORCH_CHECK(fence_mode >= 0 && fence_mode <= 2,
              "fence_mode must be 0 (clean), 1 (evict), or 2 (none)");
  auto* ptr = local.data_ptr<int32_t>();
  const int32_t stored_value = static_cast<int32_t>(value);
  const int32_t mode = static_cast<int32_t>(fence_mode);
  auto& queue = c10::xpu::getCurrentXPUStream(local.device().index()).queue();
  queue.submit([&](sycl::handler& cgh) {
    cgh.parallel_for<EsimdLocalWriteI32Kernel>(
        sycl::range<1>(1), [=](sycl::id<1>) SYCL_ESIMD_KERNEL {
          esimd_exp::lsc_block_store<int32_t,
                                     1,
                                     esimd_exp::lsc_data_size::default_size,
                                     esimd_exp::cache_hint::uncached,
                                     esimd_exp::cache_hint::write_back>(
              ptr, esimd::simd<int32_t, 1>(stored_value));
          if (mode == 0) {
            esimd::fence<esimd::memory_kind::global,
                         esimd::fence_flush_op::clean,
                         esimd::fence_scope::system>();
          } else if (mode == 1) {
            esimd::fence<esimd::memory_kind::global,
                         esimd::fence_flush_op::evict,
                         esimd::fence_scope::system>();
          } else {
            esimd::fence<esimd::memory_kind::global,
                         esimd::fence_flush_op::none,
                         esimd::fence_scope::system>();
          }
        });
  });
}

void launch_allreduce_bf16(torch::Tensor input,
                           torch::Tensor output,
                           torch::Tensor local_payload,
                           torch::Tensor local_sequence,
                           int64_t peer_payload_ptr,
                           int64_t peer_sequence_ptr,
                           torch::Tensor counter,
                           torch::Tensor status,
                           int64_t timeout_iters,
                           int64_t poll_mode,
                           int64_t barrier_rounds,
                           int64_t publish_mode,
                           int64_t queue_barrier,
                           int64_t l0_memory_barrier,
                           int64_t l0_event_scope,
                           int64_t local_ipc_event_handle,
                           int64_t peer_ipc_event_handle) {
  const at::DeviceGuard device_guard(input.device());
  CHECK_XPU(input);
  CHECK_XPU(output);
  CHECK_XPU(local_payload);
  CHECK_XPU(local_sequence);
  CHECK_XPU(counter);
  CHECK_XPU(status);
  CHECK_CONTIGUOUS(input);
  CHECK_CONTIGUOUS(output);
  CHECK_CONTIGUOUS(local_payload);
  CHECK_CONTIGUOUS(local_sequence);
  CHECK_CONTIGUOUS(counter);
  CHECK_CONTIGUOUS(status);
  TORCH_CHECK(input.scalar_type() == torch::kBFloat16,
              "input must be bfloat16");
  TORCH_CHECK(output.scalar_type() == torch::kBFloat16,
              "output must be bfloat16");
  TORCH_CHECK(local_payload.scalar_type() == torch::kBFloat16,
              "local_payload must be bfloat16");
  TORCH_CHECK(local_sequence.scalar_type() == torch::kInt32,
              "local_sequence must be int32");
  TORCH_CHECK(counter.scalar_type() == torch::kInt32,
              "counter must be int32");
  TORCH_CHECK(status.scalar_type() == torch::kInt32,
              "status must be int32");
  TORCH_CHECK(input.numel() == output.numel(),
              "input and output sizes must match");
  TORCH_CHECK(input.numel() > 0 && input.numel() % kSimd == 0,
              "input numel must be a positive multiple of ", kSimd);
  TORCH_CHECK(local_payload.dim() >= 2,
              "local_payload must have a leading ring dimension");
  TORCH_CHECK(local_payload.size(0) == local_sequence.numel(),
              "payload and sequence ring sizes must match");
  TORCH_CHECK(local_payload.numel() ==
                  local_payload.size(0) * input.numel(),
              "each payload ring slot must match input numel");
  TORCH_CHECK(local_payload.size(0) >= 3,
              "at least three payload ring slots are required");
  TORCH_CHECK(counter.numel() == 1 && status.numel() == 1,
              "counter and status must each contain one int32");
  TORCH_CHECK(peer_payload_ptr != 0 && peer_sequence_ptr != 0,
              "peer IPC pointers must be non-zero");
  TORCH_CHECK(timeout_iters > 0, "timeout_iters must be positive");
  TORCH_CHECK(poll_mode >= 0 && poll_mode <= 3,
              "poll_mode must be in [0, 3]");
  TORCH_CHECK(barrier_rounds >= 0 && barrier_rounds <= 8,
              "barrier_rounds must be in [0, 8]");
  TORCH_CHECK(publish_mode >= 0 && publish_mode <= 3,
              "publish_mode must be in [0, 3]");
  TORCH_CHECK(queue_barrier == 0 || queue_barrier == 1,
              "queue_barrier must be 0 or 1");
  TORCH_CHECK(l0_memory_barrier == 0 || l0_memory_barrier == 1,
              "l0_memory_barrier must be 0 or 1");
  TORCH_CHECK(l0_event_scope >= 0 && l0_event_scope <= 2,
              "l0_event_scope must be 0 (none), 1 (device), or 2 (host)");
  TORCH_CHECK(l0_event_scope == 0 || l0_memory_barrier == 1,
              "l0_event_scope requires l0_memory_barrier");
  TORCH_CHECK((local_ipc_event_handle == 0) == (peer_ipc_event_handle == 0),
              "local and peer IPC event handles must be provided together");

  auto* input_ptr = reinterpret_cast<bf16*>(input.data_ptr());
  auto* output_ptr = reinterpret_cast<bf16*>(output.data_ptr());
  auto* local_payload_ptr =
      reinterpret_cast<bf16*>(local_payload.data_ptr());
  auto* local_sequence_ptr = local_sequence.data_ptr<int32_t>();
  auto* peer_payload = reinterpret_cast<bf16*>(
      static_cast<uintptr_t>(peer_payload_ptr));
  auto* peer_sequence = reinterpret_cast<int32_t*>(
      static_cast<uintptr_t>(peer_sequence_ptr));
  auto* counter_ptr = counter.data_ptr<int32_t>();
  auto* status_ptr = status.data_ptr<int32_t>();
  const int32_t slots = static_cast<int32_t>(local_payload.size(0));
  const int32_t numel = static_cast<int32_t>(input.numel());
  const int32_t timeout = static_cast<int32_t>(timeout_iters);
  const int32_t polling = static_cast<int32_t>(poll_mode);
  const int32_t rounds = static_cast<int32_t>(barrier_rounds);
  const int32_t publishing = static_cast<int32_t>(publish_mode);
  const bool use_queue_barrier = queue_barrier != 0;
  const bool use_l0_memory_barrier = l0_memory_barrier != 0;

  auto& queue = c10::xpu::getCurrentXPUStream(input.device().index()).queue();
  auto publish_event = queue.submit([&](sycl::handler& cgh) {
    cgh.parallel_for<EsimdIpcPublishBf16Kernel>(
        sycl::nd_range<1>(kWorkgroup, kWorkgroup),
        [=](sycl::nd_item<1> item) SYCL_ESIMD_KERNEL {
          esimd::slm_init<kSlmBytes>();
          const int32_t tid = static_cast<int32_t>(item.get_local_linear_id());

          if (tid == 0) {
            auto counter_value =
                esimd_exp::lsc_block_load<int32_t,
                                      1,
                                      esimd_exp::lsc_data_size::default_size,
                                      esimd_exp::cache_hint::uncached,
                                      esimd_exp::cache_hint::uncached>(counter_ptr);
            const int32_t sequence = counter_value[0] + 1;
            esimd_exp::lsc_block_store<int32_t,
                                   1,
                                   esimd_exp::lsc_data_size::default_size,
                                   esimd_exp::cache_hint::uncached,
                                   esimd_exp::cache_hint::write_back>(
                counter_ptr, esimd::simd<int32_t, 1>(sequence));
            esimd_exp::lsc_block_store<int32_t,
                                   1,
                                   esimd_exp::lsc_data_size::default_size,
                                   esimd_exp::cache_hint::uncached,
                                   esimd_exp::cache_hint::write_back>(
                status_ptr, esimd::simd<int32_t, 1>(0));
            esimd::slm_scalar_store<int32_t>(0, sequence);
          }
          esimd::barrier();

          const int32_t sequence = esimd::slm_scalar_load<int32_t>(0);
          const int32_t slot = sequence % slots;
          auto* local_slot = local_payload_ptr + slot * numel;

          for (int32_t offset = tid * kSimd; offset < numel;
               offset += kWorkgroup * kSimd) {
            auto value =
                esimd_exp::lsc_block_load<bf16,
                                      kSimd,
                                      esimd_exp::lsc_data_size::default_size,
                                      esimd_exp::cache_hint::cached,
                                      esimd_exp::cache_hint::cached>(input_ptr + offset);
            esimd_exp::lsc_block_store<bf16,
                                   kSimd,
                                   esimd_exp::lsc_data_size::default_size,
                                   esimd_exp::cache_hint::uncached,
                                   esimd_exp::cache_hint::uncached>(local_slot + offset,
                                                                  value);
          }
          if (publishing == 1) {
            esimd::fence<esimd::memory_kind::global,
                         esimd::fence_flush_op::clean,
                         esimd::fence_scope::gpus>();
          } else if (publishing == 2) {
            esimd::fence<esimd::memory_kind::global,
                         esimd::fence_flush_op::evict,
                         esimd::fence_scope::gpus>();
          } else if (publishing == 3) {
            esimd::fence<esimd::memory_kind::global,
                         esimd::fence_flush_op::evict,
                         esimd::fence_scope::system>();
          } else {
            esimd::fence<esimd::memory_kind::global,
                         esimd::fence_flush_op::clean,
                         esimd::fence_scope::system>();
          }
          esimd::barrier();

          if (tid == 0) {
            esimd_exp::lsc_block_store<int32_t,
                                   1,
                                   esimd_exp::lsc_data_size::default_size,
                                   esimd_exp::cache_hint::uncached,
                                   esimd_exp::cache_hint::uncached>(
                local_sequence_ptr + slot,
                esimd::simd<int32_t, 1>(sequence));
            if (publishing == 1) {
              esimd::fence<esimd::memory_kind::global,
                           esimd::fence_flush_op::clean,
                           esimd::fence_scope::gpus>();
            } else if (publishing == 2) {
              esimd::fence<esimd::memory_kind::global,
                           esimd::fence_flush_op::evict,
                           esimd::fence_scope::gpus>();
            } else if (publishing == 3) {
              esimd::fence<esimd::memory_kind::global,
                           esimd::fence_flush_op::evict,
                           esimd::fence_scope::system>();
            } else {
              esimd::fence<esimd::memory_kind::global,
                           esimd::fence_flush_op::clean,
                           esimd::fence_scope::system>();
            }
          }
        });
  });

  ze_event_handle_t l0_signal_event = nullptr;
  const bool use_ipc_event = local_ipc_event_handle != 0;
  if (use_ipc_event) {
    auto command_list = immediate_command_list(queue);
    auto local_event = reinterpret_cast<ze_event_handle_t>(
        static_cast<uintptr_t>(local_ipc_event_handle));
    auto peer_event = reinterpret_cast<ze_event_handle_t>(
        static_cast<uintptr_t>(peer_ipc_event_handle));
    const size_t range_sizes[] = {
        static_cast<size_t>(local_payload.nbytes()),
        static_cast<size_t>(local_sequence.nbytes()),
    };
    const void* ranges[] = {
        local_payload.data_ptr(),
        local_sequence.data_ptr(),
    };
    check_ze(zeCommandListAppendMemoryRangesBarrier(command_list,
                                                     2,
                                                     range_sizes,
                                                     ranges,
                                                     local_event,
                                                     0,
                                                     nullptr),
             "zeCommandListAppendMemoryRangesBarrier(ipc signal)");
    check_ze(zeCommandListAppendWaitOnEvents(command_list, 1, &peer_event),
             "zeCommandListAppendWaitOnEvents(peer ipc event)");
  } else if (use_l0_memory_barrier) {
    l0_signal_event = append_l0_memory_ranges_barrier(
        queue, local_payload, local_sequence, l0_event_scope);
  }

  sycl::event barrier_event = publish_event;
  if (use_queue_barrier) {
    for (int32_t round = 0; round < rounds; ++round) {
      barrier_event = queue.ext_oneapi_submit_barrier({barrier_event});
    }
  } else {
    for (int32_t round = 0; round < rounds; ++round) {
      sycl::event dependency = barrier_event;
      barrier_event = queue.submit([&](sycl::handler& cgh) {
        cgh.depends_on(dependency);
        cgh.parallel_for<EsimdIpcProbeSequenceKernel>(
            sycl::range<1>(1), [=](sycl::id<1>) SYCL_ESIMD_KERNEL {
              auto counter_value =
                  esimd_exp::lsc_block_load<int32_t,
                                            1,
                                            esimd_exp::lsc_data_size::default_size,
                                            esimd_exp::cache_hint::uncached,
                                            esimd_exp::cache_hint::uncached>(counter_ptr);
              const int32_t slot = counter_value[0] % slots;
              esimd::fence<esimd::memory_kind::global,
                           esimd::fence_flush_op::none,
                           esimd::fence_scope::system_acquire>();
              auto peer_value =
                  esimd_exp::lsc_block_load<int32_t,
                                            1,
                                            esimd_exp::lsc_data_size::default_size,
                                            esimd_exp::cache_hint::uncached,
                                            esimd_exp::cache_hint::uncached>(peer_sequence + slot);
              esimd_exp::wait(peer_value);
            });
      });
    }
  }

  // B70 does not expose the mailbox write to a peer while the publishing
  // kernel is still resident. Ending that kernel is the GPU-only publication
  // boundary; this second submission can remain in the same captured graph.
  queue.submit([&](sycl::handler& cgh) {
    cgh.depends_on(barrier_event);
    cgh.parallel_for<EsimdIpcReduceBf16Kernel>(
        sycl::nd_range<1>(kWorkgroup, kWorkgroup),
        [=](sycl::nd_item<1> item) SYCL_ESIMD_KERNEL {
          esimd::slm_init<kSlmBytes>();
          const int32_t tid = static_cast<int32_t>(item.get_local_linear_id());

          if (tid == 0) {
            auto counter_value =
                esimd_exp::lsc_block_load<int32_t,
                                          1,
                                          esimd_exp::lsc_data_size::default_size,
                                          esimd_exp::cache_hint::uncached,
                                          esimd_exp::cache_hint::uncached>(counter_ptr);
            esimd::slm_scalar_store<int32_t>(0, counter_value[0]);
          }
          esimd::barrier();

          const int32_t sequence = esimd::slm_scalar_load<int32_t>(0);
          const int32_t slot = sequence % slots;
          auto* peer_slot = peer_payload + slot * numel;

          if (tid == 0) {
            int32_t seen = 0;
            int32_t attempts = 0;
            while (seen < sequence && attempts < timeout) {
              if ((polling & 1) != 0) {
                esimd::fence<esimd::memory_kind::global,
                             esimd::fence_flush_op::evict,
                             esimd::fence_scope::system_acquire>();
              } else {
                esimd::fence<esimd::memory_kind::global,
                             esimd::fence_flush_op::none,
                             esimd::fence_scope::system_acquire>();
              }
              if (polling == 2 || polling == 3) {
                auto peer_value =
                    esimd_exp::lsc_gather<int32_t,
                                          1,
                                          esimd_exp::lsc_data_size::default_size,
                                          esimd_exp::cache_hint::uncached,
                                          esimd_exp::cache_hint::uncached,
                                          1>(peer_sequence + slot, uint64_t{0});
                seen = peer_value[0];
              } else {
                auto peer_value =
                    esimd_exp::lsc_block_load<int32_t,
                                              1,
                                              esimd_exp::lsc_data_size::default_size,
                                              esimd_exp::cache_hint::uncached,
                                              esimd_exp::cache_hint::uncached>(peer_sequence + slot);
                seen = peer_value[0];
              }
              ++attempts;
            }
            const int32_t poll_status = seen < sequence ? 1 : 0;
            esimd::slm_scalar_store<int32_t>(4, poll_status);
            if (poll_status != 0) {
              esimd_exp::lsc_block_store<int32_t,
                                     1,
                                     esimd_exp::lsc_data_size::default_size,
                                     esimd_exp::cache_hint::uncached,
                                     esimd_exp::cache_hint::write_back>(
                  status_ptr, esimd::simd<int32_t, 1>(poll_status));
            }
          }
          esimd::barrier();

          const int32_t poll_status = esimd::slm_scalar_load<int32_t>(4);
          if (poll_status == 0) {
            esimd::fence<esimd::memory_kind::global,
                         esimd::fence_flush_op::none,
                         esimd::fence_scope::system_acquire>();
            for (int32_t offset = tid * kSimd; offset < numel;
                 offset += kWorkgroup * kSimd) {
              auto local_value =
                  esimd_exp::lsc_block_load<bf16,
                                        kSimd,
                                        esimd_exp::lsc_data_size::default_size,
                                        esimd_exp::cache_hint::cached,
                                        esimd_exp::cache_hint::cached>(input_ptr + offset);
              auto peer_value =
                  esimd_exp::lsc_block_load<bf16,
                                        kSimd,
                                        esimd_exp::lsc_data_size::default_size,
                                        esimd_exp::cache_hint::uncached,
                                        esimd_exp::cache_hint::uncached>(peer_slot + offset);
              esimd::simd<float, kSimd> sum = local_value;
              sum += peer_value;
              esimd::simd<bf16, kSimd> reduced = sum;
              esimd_exp::lsc_block_store<bf16,
                                     kSimd,
                                     esimd_exp::lsc_data_size::default_size,
                                     esimd_exp::cache_hint::write_back,
                                     esimd_exp::cache_hint::write_back>(output_ptr + offset,
                                                                    reduced);
            }
          }
        });
  });
  if (l0_signal_event != nullptr) {
    check_ze(zeCommandListAppendEventReset(immediate_command_list(queue),
                                           l0_signal_event),
             "zeCommandListAppendEventReset");
  }
}

}  // namespace

std::string get_ipc_handle(torch::Tensor tensor) {
  const at::DeviceGuard device_guard(tensor.device());
  CHECK_XPU(tensor);
  CHECK_CONTIGUOUS(tensor);
  ze_ipc_mem_handle_t handle = {};
  check_ze(zeMemGetIpcHandle(current_l0_context(), tensor.data_ptr(), &handle),
           "zeMemGetIpcHandle");
  return bytes_to_hex(&handle, sizeof(handle));
}

uint64_t open_ipc_handle(const std::string& handle_hex, int64_t device_index) {
  c10::xpu::set_device(static_cast<int>(device_index));
  ze_ipc_mem_handle_t handle = {};
  TORCH_CHECK(hex_to_bytes(handle_hex, &handle, sizeof(handle)),
              "invalid IPC handle hex");
  void* ptr = nullptr;
  check_ze(zeMemOpenIpcHandle(current_l0_context(),
                              l0_device_for_index(device_index),
                              handle,
                              ZE_IPC_MEMORY_FLAG_BIAS_UNCACHED,
                              &ptr),
           "zeMemOpenIpcHandle");
  return reinterpret_cast<uint64_t>(ptr);
}

uint64_t open_ipc_handle_with_mode(const std::string& handle_hex,
                                   int64_t device_index,
                                   int64_t open_mode) {
  c10::xpu::set_device(static_cast<int>(device_index));
  TORCH_CHECK(open_mode >= 0 && open_mode <= 2,
              "open_mode must be 0 (default), 1 (uncached), or 2 (cached)");
  ze_ipc_mem_handle_t handle = {};
  TORCH_CHECK(hex_to_bytes(handle_hex, &handle, sizeof(handle)),
              "invalid IPC handle hex");
  ze_ipc_memory_flags_t flags = 0;
  if (open_mode == 1) {
    flags = ZE_IPC_MEMORY_FLAG_BIAS_UNCACHED;
  } else if (open_mode == 2) {
    flags = ZE_IPC_MEMORY_FLAG_BIAS_CACHED;
  }
  void* ptr = nullptr;
  check_ze(zeMemOpenIpcHandle(current_l0_context(),
                              l0_device_for_index(device_index),
                              handle,
                              flags,
                              &ptr),
           "zeMemOpenIpcHandle");
  return reinterpret_cast<uint64_t>(ptr);
}

std::string create_ipc_event_pool(torch::Tensor tensor) {
  const at::DeviceGuard device_guard(tensor.device());
  CHECK_XPU(tensor);
  const int64_t device_index = tensor.device().index();
  TORCH_CHECK(device_index >= 0 &&
                  device_index < static_cast<int64_t>(local_ipc_events.size()),
              "unsupported XPU device index ", device_index);
  auto& state = local_ipc_events[device_index];
  TORCH_CHECK(state.pool == nullptr && state.event == nullptr,
              "local IPC event pool already exists for device ", device_index);

  ze_event_pool_desc_t pool_desc = {};
  pool_desc.stype = ZE_STRUCTURE_TYPE_EVENT_POOL_DESC;
  pool_desc.flags =
      ZE_EVENT_POOL_FLAG_IPC | ZE_EVENT_POOL_FLAG_HOST_VISIBLE;
  pool_desc.count = 1;
  auto device = l0_device_for_index(device_index);
  check_ze(zeEventPoolCreate(current_l0_context(),
                             &pool_desc,
                             1,
                             &device,
                             &state.pool),
           "zeEventPoolCreate(ipc)");

  ze_event_desc_t event_desc = {};
  event_desc.stype = ZE_STRUCTURE_TYPE_EVENT_DESC;
  event_desc.index = 0;
  event_desc.signal = ZE_EVENT_SCOPE_FLAG_HOST;
  event_desc.wait = ZE_EVENT_SCOPE_FLAG_HOST;
  check_ze(zeEventCreate(state.pool, &event_desc, &state.event),
           "zeEventCreate(ipc local)");
  check_ze(zeEventHostReset(state.event), "zeEventHostReset(ipc local)");

  ze_ipc_event_pool_handle_t handle = {};
  check_ze(zeEventPoolGetIpcHandle(state.pool, &handle),
           "zeEventPoolGetIpcHandle");
  return bytes_to_hex(&handle, sizeof(handle));
}

uint64_t local_ipc_event_handle(torch::Tensor tensor) {
  const at::DeviceGuard device_guard(tensor.device());
  CHECK_XPU(tensor);
  const int64_t device_index = tensor.device().index();
  TORCH_CHECK(device_index >= 0 &&
                  device_index < static_cast<int64_t>(local_ipc_events.size()),
              "unsupported XPU device index ", device_index);
  auto event = local_ipc_events[device_index].event;
  TORCH_CHECK(event != nullptr, "local IPC event pool has not been created");
  return reinterpret_cast<uint64_t>(event);
}

uint64_t open_ipc_event(const std::string& handle_hex) {
  ze_ipc_event_pool_handle_t handle = {};
  TORCH_CHECK(hex_to_bytes(handle_hex, &handle, sizeof(handle)),
              "invalid IPC event pool handle hex");
  L0IpcEvent state;
  check_ze(zeEventPoolOpenIpcHandle(current_l0_context(), handle, &state.pool),
           "zeEventPoolOpenIpcHandle");

  ze_event_desc_t event_desc = {};
  event_desc.stype = ZE_STRUCTURE_TYPE_EVENT_DESC;
  event_desc.index = 0;
  event_desc.signal = ZE_EVENT_SCOPE_FLAG_HOST;
  event_desc.wait = ZE_EVENT_SCOPE_FLAG_HOST;
  check_ze(zeEventCreate(state.pool, &event_desc, &state.event),
           "zeEventCreate(ipc peer)");
  opened_ipc_events.push_back(state);
  return reinterpret_cast<uint64_t>(state.event);
}

void close_ipc_event(uint64_t event_handle) {
  auto event = reinterpret_cast<ze_event_handle_t>(event_handle);
  for (auto it = opened_ipc_events.begin(); it != opened_ipc_events.end();
       ++it) {
    if (it->event == event) {
      check_ze(zeEventDestroy(it->event), "zeEventDestroy(ipc peer)");
      check_ze(zeEventPoolCloseIpcHandle(it->pool),
               "zeEventPoolCloseIpcHandle");
      opened_ipc_events.erase(it);
      return;
    }
  }
  TORCH_CHECK(false, "unknown opened IPC event handle");
}

void destroy_local_ipc_event(torch::Tensor tensor) {
  const at::DeviceGuard device_guard(tensor.device());
  CHECK_XPU(tensor);
  const int64_t device_index = tensor.device().index();
  auto& state = local_ipc_events[device_index];
  TORCH_CHECK(state.event != nullptr && state.pool != nullptr,
              "local IPC event pool has not been created");
  check_ze(zeEventDestroy(state.event), "zeEventDestroy(ipc local)");
  check_ze(zeEventPoolDestroy(state.pool), "zeEventPoolDestroy(ipc local)");
  state = {};
}

std::string create_ipc_event_pair_pool(torch::Tensor tensor) {
  const at::DeviceGuard device_guard(tensor.device());
  CHECK_XPU(tensor);
  const int64_t device_index = tensor.device().index();
  TORCH_CHECK(device_index >= 0 && device_index <
                  static_cast<int64_t>(local_ipc_event_pairs.size()),
              "unsupported XPU device index ", device_index);
  auto& state = local_ipc_event_pairs[device_index];
  TORCH_CHECK(state.pool == nullptr,
              "local IPC event pair already exists for device ", device_index);

  ze_event_pool_desc_t pool_desc = {};
  pool_desc.stype = ZE_STRUCTURE_TYPE_EVENT_POOL_DESC;
  pool_desc.flags =
      ZE_EVENT_POOL_FLAG_IPC | ZE_EVENT_POOL_FLAG_HOST_VISIBLE;
  pool_desc.count = 2;
  auto device = l0_device_for_index(device_index);
  check_ze(zeEventPoolCreate(current_l0_context(),
                             &pool_desc,
                             1,
                             &device,
                             &state.pool),
           "zeEventPoolCreate(ipc pair)");

  for (uint32_t index = 0; index < state.events.size(); ++index) {
    ze_event_desc_t event_desc = {};
    event_desc.stype = ZE_STRUCTURE_TYPE_EVENT_DESC;
    event_desc.index = index;
    event_desc.signal = ZE_EVENT_SCOPE_FLAG_HOST;
    event_desc.wait = ZE_EVENT_SCOPE_FLAG_HOST;
    check_ze(zeEventCreate(state.pool, &event_desc, &state.events[index]),
             "zeEventCreate(ipc pair local)");
    check_ze(zeEventHostReset(state.events[index]),
             "zeEventHostReset(ipc pair local)");
  }

  ze_ipc_event_pool_handle_t handle = {};
  check_ze(zeEventPoolGetIpcHandle(state.pool, &handle),
           "zeEventPoolGetIpcHandle(pair)");
  return bytes_to_hex(&handle, sizeof(handle));
}

std::vector<uint64_t> local_ipc_event_pair_handles(torch::Tensor tensor) {
  const at::DeviceGuard device_guard(tensor.device());
  CHECK_XPU(tensor);
  auto& state = local_ipc_event_pairs[tensor.device().index()];
  TORCH_CHECK(state.pool != nullptr, "local IPC event pair has not been created");
  return {reinterpret_cast<uint64_t>(state.events[0]),
          reinterpret_cast<uint64_t>(state.events[1])};
}

std::vector<uint64_t> open_ipc_event_pair(const std::string& handle_hex) {
  ze_ipc_event_pool_handle_t handle = {};
  TORCH_CHECK(hex_to_bytes(handle_hex, &handle, sizeof(handle)),
              "invalid IPC event pair handle hex");
  L0IpcEventPair state;
  check_ze(zeEventPoolOpenIpcHandle(current_l0_context(), handle, &state.pool),
           "zeEventPoolOpenIpcHandle(pair)");
  for (uint32_t index = 0; index < state.events.size(); ++index) {
    ze_event_desc_t event_desc = {};
    event_desc.stype = ZE_STRUCTURE_TYPE_EVENT_DESC;
    event_desc.index = index;
    event_desc.signal = ZE_EVENT_SCOPE_FLAG_HOST;
    event_desc.wait = ZE_EVENT_SCOPE_FLAG_HOST;
    check_ze(zeEventCreate(state.pool, &event_desc, &state.events[index]),
             "zeEventCreate(ipc pair peer)");
  }
  opened_ipc_event_pairs.push_back(state);
  return {reinterpret_cast<uint64_t>(state.events[0]),
          reinterpret_cast<uint64_t>(state.events[1])};
}

void close_ipc_event_pair(uint64_t first_event_handle) {
  auto first = reinterpret_cast<ze_event_handle_t>(first_event_handle);
  for (auto it = opened_ipc_event_pairs.begin();
       it != opened_ipc_event_pairs.end(); ++it) {
    if (it->events[0] == first) {
      for (auto event : it->events) {
        check_ze(zeEventDestroy(event), "zeEventDestroy(ipc pair peer)");
      }
      check_ze(zeEventPoolCloseIpcHandle(it->pool),
               "zeEventPoolCloseIpcHandle(pair)");
      opened_ipc_event_pairs.erase(it);
      return;
    }
  }
  TORCH_CHECK(false, "unknown opened IPC event pair handle");
}

void destroy_local_ipc_event_pair(torch::Tensor tensor) {
  const at::DeviceGuard device_guard(tensor.device());
  CHECK_XPU(tensor);
  auto& state = local_ipc_event_pairs[tensor.device().index()];
  TORCH_CHECK(state.pool != nullptr, "local IPC event pair has not been created");
  for (auto event : state.events) {
    check_ze(zeEventDestroy(event), "zeEventDestroy(ipc pair local)");
  }
  check_ze(zeEventPoolDestroy(state.pool),
           "zeEventPoolDestroy(ipc pair local)");
  state = {};
}

std::vector<uint64_t> create_external_counter_event_pair(
    torch::Tensor local_counter,
    int64_t peer_counter_ptr) {
  const at::DeviceGuard device_guard(local_counter.device());
  CHECK_XPU(local_counter);
  CHECK_CONTIGUOUS(local_counter);
  TORCH_CHECK(local_counter.scalar_type() == torch::kInt64 &&
                  local_counter.numel() == 1,
              "local_counter must contain one XPU int64");
  TORCH_CHECK(peer_counter_ptr != 0, "peer_counter_ptr must be non-zero");

  auto device = l0_device_for_index(local_counter.device().index());
  std::array<uint64_t*, 2> addresses = {
      reinterpret_cast<uint64_t*>(local_counter.data_ptr<int64_t>()),
      reinterpret_cast<uint64_t*>(static_cast<uintptr_t>(peer_counter_ptr)),
  };
  std::array<ze_event_handle_t, 2> events = {nullptr, nullptr};
  for (size_t index = 0; index < events.size(); ++index) {
    ze_event_counter_based_external_sync_allocation_desc_t external_desc = {};
    external_desc.stype =
        ZE_STRUCTURE_TYPE_EVENT_COUNTER_BASED_EXTERNAL_SYNC_ALLOCATION_DESC;
    external_desc.deviceAddress = addresses[index];
    external_desc.hostAddress = nullptr;
    external_desc.completionValue = 1;

    ze_event_counter_based_desc_t event_desc = {};
    event_desc.stype = ZE_STRUCTURE_TYPE_EVENT_COUNTER_BASED_DESC;
    event_desc.pNext = &external_desc;
    event_desc.flags = ZE_EVENT_COUNTER_BASED_FLAG_IMMEDIATE;
    event_desc.signal = ZE_EVENT_SCOPE_FLAG_HOST;
    event_desc.wait = ZE_EVENT_SCOPE_FLAG_HOST;
    check_ze(zeEventCounterBasedCreate(current_l0_context(),
                                        device,
                                        &event_desc,
                                        &events[index]),
             "zeEventCounterBasedCreate(external)");
  }
  external_counter_event_pairs.push_back(events);
  return {reinterpret_cast<uint64_t>(events[0]),
          reinterpret_cast<uint64_t>(events[1])};
}

void destroy_external_counter_event_pair(uint64_t first_event_handle) {
  auto first = reinterpret_cast<ze_event_handle_t>(first_event_handle);
  for (auto it = external_counter_event_pairs.begin();
       it != external_counter_event_pairs.end(); ++it) {
    if ((*it)[0] == first) {
      for (auto event : *it) {
        check_ze(zeEventDestroy(event),
                 "zeEventDestroy(external counter event)");
      }
      external_counter_event_pairs.erase(it);
      return;
    }
  }
  TORCH_CHECK(false, "unknown external counter event pair handle");
}

void close_ipc_handle(uint64_t ptr, int64_t device_index) {
  c10::xpu::set_device(static_cast<int>(device_index));
  check_ze(zeMemCloseIpcHandle(current_l0_context(),
                               reinterpret_cast<void*>(ptr)),
           "zeMemCloseIpcHandle");
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
  m.def("get_ipc_handle", &get_ipc_handle);
  m.def("open_ipc_handle", &open_ipc_handle);
  m.def("open_ipc_handle_with_mode", &open_ipc_handle_with_mode);
  m.def("create_ipc_event_pool", &create_ipc_event_pool);
  m.def("local_ipc_event_handle", &local_ipc_event_handle);
  m.def("open_ipc_event", &open_ipc_event);
  m.def("close_ipc_event", &close_ipc_event);
  m.def("destroy_local_ipc_event", &destroy_local_ipc_event);
  m.def("create_ipc_event_pair_pool", &create_ipc_event_pair_pool);
  m.def("local_ipc_event_pair_handles", &local_ipc_event_pair_handles);
  m.def("open_ipc_event_pair", &open_ipc_event_pair);
  m.def("close_ipc_event_pair", &close_ipc_event_pair);
  m.def("destroy_local_ipc_event_pair", &destroy_local_ipc_event_pair);
  m.def("create_external_counter_event_pair",
        &create_external_counter_event_pair);
  m.def("destroy_external_counter_event_pair",
        &destroy_external_counter_event_pair);
  m.def("close_ipc_handle", &close_ipc_handle);
  m.def("allreduce_bf16", &launch_allreduce_bf16);
  m.def("native_queue_kind", &native_queue_kind);
  m.def("read_peer_i32", &read_peer_i32);
  m.def("write_local_i32", &write_local_i32);
}
