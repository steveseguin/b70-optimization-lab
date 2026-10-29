// CPU-only unit test (research/tp/fault-ladder-2026-10-29): the DPC++ fast-kernel-cache thrash of one SYCL context shared
// by two devices, and the per-card-context remedy (OWNRT_TP_CARD_CONTEXT=1 in single_device.cpp). OpenCL CPU device split
// into two sub-devices; no GPU is opened.
//   source /opt/intel/oneapi/setvars.sh
//   icpx -fsycl -std=gnu++20 -O1 fast_cache_unit_test.cpp -o /dev/shm/fault-ladder-20261029/fast_cache_unit_test
//   ONEAPI_DEVICE_SELECTOR=opencl:cpu /dev/shm/fault-ladder-20261029/fast_cache_unit_test
// Mechanism (libsycl 2026.0, KernelProgramCache::saveKernel; unchanged at intel/llvm HEAD): a fast-cache miss saves the
// kernel; saveKernel appends {name, device} to MProgramToFastKernelCacheKeyMap[program] (never trimmed while the program
// lives) and, when the name is already in this context's MFastKernelCache, destroys a temporary FastKernelSubcacheWrapper
// whose destructor erases EVERY subcache entry of this context, the other device's included. Two devices of one context
// submitting the same kernel therefore miss on every alternation: one 24-byte record per submission, unbounded.
// Heap = mallinfo2 (all arenas), steady-state slope over a second interval of `rounds` rounds after warm-up.
// Checks: (1) shared context, alternating queues: heap grows by >= 16 B per submission (the record); (2) per-card contexts (each with both devices, as the engine's fix): heap growth < 1 B per submission;
// (3) one queue alone in the shared context: no growth (one card's behaviour); (4) results equal in all forms.
#include <sycl/sycl.hpp>
#include <malloc.h>
#include <chrono>
#include <cstdio>
#include <vector>

static long heap() { struct mallinfo2 m = mallinfo2(); return long(m.uordblks + m.hblkhd); }
struct Result { double bytes_per_submit, ns_per_submit; unsigned sum; };

static Result run(std::vector<sycl::queue>& qs, int rounds) {
  std::vector<unsigned*> out;
  for (auto& q : qs) { out.push_back(sycl::malloc_device<unsigned>(1, q)); q.memset(out.back(), 0, 4).wait(); }
  auto step = [&](int r) {
    for (size_t i = 0; i < qs.size(); ++i) {
      unsigned* p = out[i];
      qs[i].submit([&](sycl::handler& h) { h.single_task<class FastCacheProbe>([=] { *p += 1u; }); });
    }
    if (r % 256 == 255) for (auto& q : qs) q.wait();
  };
  // Warm (programs built, caches and runtime pools populated), then a first interval whose growth is not counted (fixed
  // warm-up costs); the steady-state slope is the second interval's growth.
  for (int r = 0; r < 2048; ++r) step(r);
  for (auto& q : qs) q.wait();
  for (int r = 0; r < rounds; ++r) step(r);
  for (auto& q : qs) q.wait();
  const long h0 = heap(); const auto t0 = std::chrono::steady_clock::now();
  for (int r = 0; r < rounds; ++r) step(r);
  for (auto& q : qs) q.wait();
  const double ns = std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - t0).count();
  const long h1 = heap();
  unsigned sum = 0;
  for (size_t i = 0; i < qs.size(); ++i) { unsigned v = 0; qs[i].memcpy(&v, out[i], 4).wait(); sum += v; sycl::free(out[i], qs[i]); }
  const double n = double(rounds) * qs.size();
  return {double(h1 - h0) / n, ns / n, sum};
}

int main() {
  sycl::device cpu{sycl::cpu_selector_v};
  const auto units = cpu.get_info<sycl::info::device::max_compute_units>();
  auto subs = cpu.create_sub_devices<sycl::info::partition_property::partition_equally>(units / 2);
  if (subs.size() < 2) { std::printf("FAIL: no two sub-devices\n"); return 1; }
  std::vector<sycl::device> two{subs[0], subs[1]};
  const sycl::property_list in_order{sycl::property::queue::in_order{}};
  const int rounds = 40000;
  int failures = 0;
  auto check = [&](bool ok, const char* what) { std::printf("%s: %s\n", ok ? "pass" : "FAIL", what); failures += !ok; };

  // (1) one context shared by both devices (today's TP group).
  Result shared;
  { sycl::context ctx(two); std::vector<sycl::queue> qs{sycl::queue(ctx, two[0], in_order), sycl::queue(ctx, two[1], in_order)};
    shared = run(qs, rounds); }
  // (2) one context per card, each holding both devices (the fix).
  Result per_card;
  { sycl::context a(two), b(two); std::vector<sycl::queue> qs{sycl::queue(a, two[0], in_order), sycl::queue(b, two[1], in_order)};
    per_card = run(qs, rounds); }
  // (3) one queue alone in a two-device context (a single card's submission stream).
  Result alone;
  { sycl::context ctx(two); std::vector<sycl::queue> qs{sycl::queue(ctx, two[0], in_order)};
    alone = run(qs, rounds); }

  std::printf("shared context, two queues : %.2f heap bytes / submission, %.0f ns / submission\n", shared.bytes_per_submit, shared.ns_per_submit);
  std::printf("per-card contexts          : %.2f heap bytes / submission, %.0f ns / submission\n", per_card.bytes_per_submit, per_card.ns_per_submit);
  std::printf("one queue alone            : %.2f heap bytes / submission, %.0f ns / submission\n", alone.bytes_per_submit, alone.ns_per_submit);
  check(shared.bytes_per_submit >= 16.0, "shared context grows the heap by a record per submission (the runtime defect reproduced)");
  check(per_card.bytes_per_submit < 1.0, "per-card contexts: no per-submission growth");
  check(alone.bytes_per_submit < 1.0, "one queue alone: no per-submission growth");
  const unsigned want = 2u * unsigned(2 * rounds + 2048);
  check(shared.sum == want && per_card.sum == want && alone.sum == want / 2, "results equal in every form");
  std::printf("%d failures\n", failures);
  return failures ? 1 : 0;
}
