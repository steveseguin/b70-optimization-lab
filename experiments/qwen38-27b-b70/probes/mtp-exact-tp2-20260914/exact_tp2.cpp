// Experimental host-ordered, out-of-place FP16 TP2 collective building blocks.
// No device peer spin, remote events, compression, or model integration.
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <cstdint>
#include <cstring>
#include <exception>
#include <string>

namespace {
thread_local std::string error;
sycl::queue& queue(uintptr_t p) {
  if (!p) throw std::runtime_error("null SYCL queue");
  auto& q = *reinterpret_cast<sycl::queue*>(p);
  if (!q.is_in_order()) throw std::runtime_error("requires in-order queue");
  if (q.get_backend() != sycl::backend::ext_oneapi_level_zero)
    throw std::runtime_error("requires Level Zero backend");
  return q;
}
auto context(sycl::queue& q) {
  return sycl::get_native<sycl::backend::ext_oneapi_level_zero>(q.get_context());
}
auto device(sycl::queue& q) {
  return sycl::get_native<sycl::backend::ext_oneapi_level_zero>(q.get_device());
}
void checked(ze_result_t r) {
  if (r != ZE_RESULT_SUCCESS)
    throw std::runtime_error("Level Zero result " + std::to_string(r));
}
template<class F> int protect(F f) {
  try { f(); return 0; }
  catch (const std::exception& e) { error = e.what(); return -1; }
}
uintptr_t event(sycl::event e) { return reinterpret_cast<uintptr_t>(new sycl::event(e)); }
}
extern "C" {
const char* et_error() { return error.c_str(); }
int et_device_uuid(uintptr_t qp, void* uuid16) {
  return protect([&] {
    auto& q = queue(qp); ze_device_properties_t p{};
    p.stype = ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;
    checked(zeDeviceGetProperties(device(q), &p));
    std::memcpy(uuid16, p.uuid.id, ZE_MAX_DEVICE_UUID_SIZE);
  });
}
int et_admit_peer(uintptr_t qp, const void* uuid16) {
  return protect([&] {
    auto& q = queue(qp);
    for (const auto& peer : q.get_context().get_devices()) {
      auto pd = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(peer);
      ze_device_properties_t p{}; p.stype = ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;
      checked(zeDeviceGetProperties(pd, &p));
      if (std::memcmp(uuid16, p.uuid.id, ZE_MAX_DEVICE_UUID_SIZE) == 0) {
        if (pd == device(q)) throw std::runtime_error("TP2 ranks selected same device");
        ze_bool_t access = false;
        checked(zeDeviceCanAccessPeer(device(q), pd, &access));
        if (!access) throw std::runtime_error("peer memory access unsupported");
        return;
      }
    }
    throw std::runtime_error("peer UUID not in local SYCL context");
  });
}
int et_validate_fd(uintptr_t qp, const void* handle64) {
  return protect([&] {
    auto& q = queue(qp); uint64_t fd = 0; int first = -1;
    std::memcpy(&first, handle64, sizeof(first));
    checked(zeMemGetFileDescriptorFromIpcHandleExp(context(q), *reinterpret_cast<const ze_ipc_mem_handle_t*>(handle64), &fd));
    if (first < 0 || fd != static_cast<uint64_t>(first))
      throw std::runtime_error("unqualified Linux IPC handle FD layout");
  });
}
int et_allocate(uintptr_t qp, size_t bytes, uintptr_t* out) {
  return protect([&] {
    auto& q = queue(qp);
    if (!bytes || bytes % 2) throw std::runtime_error("invalid FP16 allocation length");
    ze_device_mem_alloc_desc_t desc{};
    desc.stype = ZE_STRUCTURE_TYPE_DEVICE_MEM_ALLOC_DESC;
    void* p = nullptr;
    checked(zeMemAllocDevice(context(q), &desc, bytes, 64, device(q), &p));
    // Native allocations must also be recognized by the active SYCL/UR
    // adapter. Do not submit a kernel with an unrecognized interop pointer.
    if (sycl::get_pointer_type(p, q.get_context()) != sycl::usm::alloc::device) {
      checked(zeMemFree(context(q), p));
      throw std::runtime_error("SYCL adapter does not admit native device allocation");
    }
    *out = reinterpret_cast<uintptr_t>(p);
  });
}
int et_free(uintptr_t qp, uintptr_t ptr) {
  return protect([&] { auto& q = queue(qp); checked(zeMemFree(context(q), reinterpret_cast<void*>(ptr))); });
}
int et_export(uintptr_t qp, uintptr_t ptr, void* handle64) {
  return protect([&] { auto& q = queue(qp); checked(zeMemGetIpcHandle(context(q), reinterpret_cast<void*>(ptr), reinterpret_cast<ze_ipc_mem_handle_t*>(handle64))); });
}
int et_put_export(uintptr_t qp, const void* handle64) {
  return protect([&] { auto& q = queue(qp); checked(zeMemPutIpcHandle(context(q), *reinterpret_cast<const ze_ipc_mem_handle_t*>(handle64))); });
}
int et_open(uintptr_t qp, const void* handle64, uintptr_t* out) {
  return protect([&] {
    auto& q = queue(qp); void* p = nullptr;
    checked(zeMemOpenIpcHandle(context(q), device(q), *reinterpret_cast<const ze_ipc_mem_handle_t*>(handle64), 0, &p));
    if (sycl::get_pointer_type(p, q.get_context()) != sycl::usm::alloc::device) {
      checked(zeMemCloseIpcHandle(context(q), p));
      throw std::runtime_error("SYCL adapter does not admit native IPC device allocation");
    }
    *out = reinterpret_cast<uintptr_t>(p);
  });
}
int et_close(uintptr_t qp, uintptr_t ptr) {
  return protect([&] { auto& q = queue(qp); checked(zeMemCloseIpcHandle(context(q), reinterpret_cast<void*>(ptr))); });
}
int et_marker(uintptr_t qp, uintptr_t* ep) {
  return protect([&] { *ep = event(queue(qp).ext_oneapi_submit_barrier()); });
}
int et_copy(uintptr_t qp, uintptr_t dst, uintptr_t src, size_t bytes, uintptr_t* ep) {
  return protect([&] {
    if (!src || !dst || src == dst || !bytes) throw std::runtime_error("invalid copy");
    *ep = event(queue(qp).memcpy(reinterpret_cast<void*>(dst), reinterpret_cast<void*>(src), bytes));
  });
}
int et_add(uintptr_t qp, uintptr_t local, uintptr_t output, size_t n, int rank, uintptr_t* ep) {
  return protect([&] {
    if (!local || !output || local == output || !n || (rank != 0 && rank != 1))
      throw std::runtime_error("invalid add");
    auto* a = reinterpret_cast<const sycl::half*>(local);
    auto* b = reinterpret_cast<sycl::half*>(output);
    *ep = event(queue(qp).parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) {
      // Fixed rank order, FP32 add, one FP16 rounding. Runtime XCCL bit equality
      // (including signed zeros/subnormals/NaNs) is mandatory, not assumed.
      float x = static_cast<float>(rank == 0 ? a[i] : b[i]);
      float y = static_cast<float>(rank == 0 ? b[i] : a[i]);
      b[i] = static_cast<sycl::half>(x + y);
    }));
  });
}
int et_poll(uintptr_t ep, int* complete) {
  return protect([&] {
    auto& e = *reinterpret_cast<sycl::event*>(ep);
    *complete = e.get_info<sycl::info::event::command_execution_status>() == sycl::info::event_command_status::complete;
    if (*complete) e.wait_and_throw();
  });
}
int et_release_event(uintptr_t ep) {
  return protect([&] { delete reinterpret_cast<sycl::event*>(ep); });
}
}
