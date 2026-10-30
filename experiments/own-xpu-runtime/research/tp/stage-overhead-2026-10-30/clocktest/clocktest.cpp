// Device-clock probe for the stage-overhead lab (2026-10-30). One card, no TP, no peer memory, no profiler.
// 1. aspects: ext_oneapi_clock_device / work_group / sub_group;
// 2. device clock rate: clock<device>() in two single_task kernels separated by a host sleep, against steady_clock;
// 3. device-wide consistency: 64 work-groups of a trivial kernel read the clock once each (spread in ticks);
// 4. poll cost: one work-item runs N system-scope relaxed atomic loads of a local device word (the exchange wait loop's
//    load), timed with the device clock -> ns per poll (converts retained poll_sum counters to time).
// Output: one JSON line on stdout.
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/experimental/clock.hpp>
#include <chrono>
#include <cstdio>
#include <thread>
#include <vector>
namespace X = sycl::ext::oneapi::experimental;
using u32 = std::uint32_t;
using u64 = std::uint64_t;

int main() {
  auto devs = sycl::device::get_devices(sycl::info::device_type::gpu);
  if (devs.size() != 1) { std::printf("{\"error\":\"expected exactly one visible GPU, got %zu\"}\n", devs.size()); return 2; }
  sycl::device d = devs[0];
  const bool cd = d.has(sycl::aspect::ext_oneapi_clock_device), cw = d.has(sycl::aspect::ext_oneapi_clock_work_group),
             cs = d.has(sycl::aspect::ext_oneapi_clock_sub_group);
  std::printf("{\"device\":\"%s\",\"clock_device\":%d,\"clock_work_group\":%d,\"clock_sub_group\":%d",
              d.get_info<sycl::info::device::name>().c_str(), cd, cw, cs);
  if (!cs) { std::printf(",\"note\":\"no sub-group clock\"}\n"); return 0; }
  // device scope is not offered on B70 (2026-10-30 probe); every read below is the sub-group (EU thread) clock
  sycl::queue q(d, sycl::property::queue::in_order{});
  u64* t = sycl::malloc_device<u64>(256, q);
  u64 h[256];
  // 2. rate
  std::printf(",\"rate\":[");
  for (int r = 0; r < 5; ++r) {
    q.single_task([=] { t[0] = X::clock<X::clock_scope::sub_group>(); }).wait();
    auto h0 = std::chrono::steady_clock::now();
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    auto h1 = std::chrono::steady_clock::now();
    q.single_task([=] { t[1] = X::clock<X::clock_scope::sub_group>(); }).wait();
    q.memcpy(h, t, 2 * sizeof(u64)).wait();
    const double ns = std::chrono::duration<double, std::nano>(h1 - h0).count();
    std::printf("%s{\"ticks\":%llu,\"host_ns_inner\":%.0f,\"ticks_per_ns\":%.6f}", r ? "," : "",
                (unsigned long long)(h[1] - h[0]), ns, double(h[1] - h[0]) / ns);
  }
  std::printf("]");
  // 3. consistency across 64 work-groups (each group's item 0 reads once)
  q.parallel_for(sycl::nd_range<1>(64 * 256, 256), [=](sycl::nd_item<1> it) {
    if (it.get_local_linear_id() == 0) t[it.get_group_linear_id()] = X::clock<X::clock_scope::sub_group>();
  }).wait();
  q.memcpy(h, t, 64 * sizeof(u64)).wait();
  u64 lo = h[0], hi = h[0];
  for (int i = 0; i < 64; ++i) { lo = std::min(lo, h[i]); hi = std::max(hi, h[i]); }
  std::printf(",\"groups64_spread_ticks\":%llu", (unsigned long long)(hi - lo));
  // 4. poll cost: N system-scope atomic loads of a local device word (never satisfied), clocked on device
  u32* flag = sycl::malloc_device<u32>(64, q);
  q.memset(flag, 0, 64 * sizeof(u32)).wait();
  std::printf(",\"poll\":[");
  const u32 Ns[] = {1000, 10000, 100000};
  for (int k = 0; k < 3; ++k) {
    const u32 N = Ns[k];
    q.single_task([=] {
      using sys_ref = sycl::atomic_ref<u32, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                       sycl::access::address_space::global_space>;
      sys_ref f(flag[16]);
      u32 polls = 0, v = f.load();
      const u64 a = X::clock<X::clock_scope::sub_group>();
      while (v < 1u && polls < N) { ++polls; v = f.load(); }
      const u64 b = X::clock<X::clock_scope::sub_group>();
      t[0] = b - a; t[1] = polls;
    }).wait();
    q.memcpy(h, t, 2 * sizeof(u64)).wait();
    std::printf("%s{\"polls\":%llu,\"ticks\":%llu}", k ? "," : "", (unsigned long long)h[1], (unsigned long long)h[0]);
  }
  std::printf("]");
  // 5. rate inside one kernel: a 20 ms-ish poll spin timed by the sub-group clock and by the host around .wait()
  std::printf(",\"spin\":[");
  for (int r = 0; r < 3; ++r) {
    const u32 N = 200000u;
    auto h0 = std::chrono::steady_clock::now();
    q.single_task([=] {
      using sys_ref = sycl::atomic_ref<u32, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                       sycl::access::address_space::global_space>;
      sys_ref f(flag[16]);
      u32 polls = 0, v = f.load();
      const u64 a = X::clock<X::clock_scope::sub_group>();
      while (v < 1u && polls < N) { ++polls; v = f.load(); }
      const u64 b = X::clock<X::clock_scope::sub_group>();
      t[0] = b - a; t[1] = polls;
    }).wait();
    auto h1 = std::chrono::steady_clock::now();
    q.memcpy(h, t, 2 * sizeof(u64)).wait();
    std::printf("%s{\"polls\":%llu,\"ticks\":%llu,\"host_ns\":%.0f}", r ? "," : "", (unsigned long long)h[1], (unsigned long long)h[0],
                std::chrono::duration<double, std::nano>(h1 - h0).count());
  }
  std::printf("]}\n");
  sycl::free(flag, q); sycl::free(t, q);
  return 0;
}
