// CPU unit test of the exact vocabulary-row head split for both users of draft_head_split.hpp:
//   target head (OWNRT_TARGET_HEAD_SPLIT=1): F32 logits, records at base 0 of an 8-word pair buffer, merged on BOTH cards;
//   draft head  (OWNRT_DRAFT_HEAD_SPLIT=1):  BF16 logits, records at base 4 of the 16-word split words, merged on card 0
//   (a regression check of the kernels after their F32 generalisation).
// The merged result of two shards (card 0: rows [0, r0), card 1: rows [r0, R)) must equal the one-card ArgmaxFast result
// over all R rows: the largest value, the lowest index among equal values (+0 == -0), and a sticky failure if any logit is
// non-finite. Compared on every case:
//   (1) ref:   a plain sequential definition (first strictly larger value wins; any non-finite fails);
//   (2) fast:  a verbatim copy of ArgmaxFast's device body (adapter.cpp: one 1024-lane work-group; View::get), run as SYCL;
//   (3) split: the engine's own ShardKernelT<T> (each half) and MergeKernel device functors, run as SYCL kernels on the
//              OpenCL CPU device, the record exchange as the direct exchange does it (own slot to the peer's same slot),
//              and the host twins draft_split::shard / draft_split::merge.
// No GPU is opened:
//   source /opt/intel/oneapi/setvars.sh
//   icpx -fsycl -std=gnu++20 -O1 -fno-fast-math -ffp-contract=off -I ../../../engine/src head_unit_test.cpp -o /dev/shm/head_unit_test
//   ONEAPI_DEVICE_SELECTOR=opencl:cpu /dev/shm/head_unit_test
#include "stage2/packet194-expert-diet-engine/draft_head_split.hpp"
#include <cfloat>
#include <cstdio>
#include <random>
#include <string>
#include <vector>

using u16 = uint16_t;
struct Result { int index; bool fail; };
template <class T> static T from_float(float f) { if constexpr (std::is_same_v<T, float>) return f; else return u16(std::bit_cast<uint32_t>(f) >> 16); }
template <class T> static T from_bits(uint32_t u) { if constexpr (std::is_same_v<T, float>) return std::bit_cast<float>(u); else return u16(u >> 16); }

template <class T> static Result ref(const std::vector<T>& x) {
  int best = 0; bool finite = true;
  for (size_t j = 0; j < x.size(); ++j) { const float v = draft_split::logit_value(x[j]); finite = finite && std::isfinite(v); if (v > draft_split::logit_value(x[best])) best = int(j); }
  return {best, !finite};
}
// ArgmaxFast (adapter.cpp), verbatim body with raw pointers for rb.in(0)/rb.out(0)/rb.fail(): one row, W = 1024.
template <class T> struct ArgmaxFastCopy {
  const T* in; int n; int32_t* out; uint32_t* error;
  void operator()(sycl::nd_item<1> it) const {
    const int lane = int(it.get_local_linear_id()); auto g = it.get_group();
    constexpr int W = 1024; auto get = [&](int j) { return draft_split::logit_value(in[j]); };
    int best = -1; float value = 0.f; bool finite = true;
    for (int j = lane; j < n; j += W) { const float v = get(j); finite = finite && sycl::isfinite(v); if (best < 0 || v > value) { best = j; value = v; } }
    const bool all_finite = sycl::all_of_group(g, finite);
    if (all_finite) {
      const float top = sycl::reduce_over_group(g, best < 0 ? -INFINITY : value, sycl::maximum<float>());
      const int index = sycl::reduce_over_group(g, (best >= 0 && value == top) ? best : INT_MAX, sycl::minimum<int>());
      if (lane == 0) *out = int32_t(float(index));
    } else if (lane == 0) {
      int fallback = 0;
      for (int l = 0; l < 128; ++l) { int local = l; for (int j = l; j < n; j += 128) if (get(j) > get(local)) local = j;
        if (l < n && (get(local) > get(fallback) || (get(local) == get(fallback) && local < fallback))) fallback = local; }
      *out = int32_t(float(fallback)); *error = 1;
    }
  }
};

struct Device {
  sycl::queue q{sycl::cpu_selector_v, sycl::property::queue::in_order{}};
  template <class T> Result fast(const std::vector<T>& x) {
    T* in = sycl::malloc_shared<T>(x.size(), q); int32_t* out = sycl::malloc_shared<int32_t>(1, q); uint32_t* err = sycl::malloc_shared<uint32_t>(1, q);
    std::copy(x.begin(), x.end(), in); *out = -7; *err = 0;
    q.parallel_for(sycl::nd_range<1>(1024, 1024), ArgmaxFastCopy<T>{in, int(x.size()), out, err}).wait();
    Result r{*out, *err != 0}; sycl::free(in, q); sycl::free(out, q); sycl::free(err, q); return r;
  }
  // The engine's kernels on two simulated cards: shard (card c: its own compact logits, offset r0 for card 1, slot c),
  // the record exchange (slot c to the peer's slot c), then the merge on card 0 and on card 1 (both must agree).
  template <class T> Result split(const std::vector<T>& x, uint32_t r0, uint32_t base, uint32_t words, bool preset0, bool preset1, uint32_t* records, int* token1) {
    const uint32_t r1 = uint32_t(x.size()) - r0;
    T* l0 = sycl::malloc_shared<T>(r0, q); T* l1 = sycl::malloc_shared<T>(r1, q);
    uint32_t* w[2] = {sycl::malloc_shared<uint32_t>(words, q), sycl::malloc_shared<uint32_t>(words, q)};
    uint32_t* ctl = sycl::malloc_shared<uint32_t>(4, q);  // active0, error0, active1, error1
    int32_t* token = sycl::malloc_shared<int32_t>(2, q);
    std::copy(x.begin(), x.begin() + r0, l0); std::copy(x.begin() + r0, x.end(), l1);
    for (int c = 0; c < 2; ++c) for (unsigned i = 0; i < words; ++i) w[c][i] = 0xdeadbeefu;  // stale garbage must never be read
    ctl[0] = 1; ctl[1] = preset0; ctl[2] = 1; ctl[3] = preset1; token[0] = token[1] = -7;
    draft_split::ShardKernelT<T> s0{l0, w[0], ctl + 0, ctl + 1, r0, 0, 0, base}, s1{l1, w[1], ctl + 2, ctl + 3, r1, r0, 1, base};
    q.parallel_for(sycl::nd_range<1>(draft_split::lanes, draft_split::lanes), s0).wait();
    q.parallel_for(sycl::nd_range<1>(draft_split::lanes, draft_split::lanes), s1).wait();
    for (int c = 0; c < 2; ++c) for (unsigned i = 0; i < 4; ++i) w[1 - c][base + 4 * c + i] = w[c][base + 4 * c + i];  // the exchange
    if (records) for (unsigned i = 0; i < 8; ++i) records[i] = w[0][base + i];
    q.parallel_for(sycl::range<1>(1), draft_split::MergeKernel{w[0], token + 0, ctl + 0, ctl + 1, base}).wait();
    q.parallel_for(sycl::range<1>(1), draft_split::MergeKernel{w[1], token + 1, ctl + 2, ctl + 3, base}).wait();
    Result r{token[0], ctl[1] != 0}; if (token1) *token1 = (ctl[3] != 0) != r.fail ? -99 : token[1];
    for (void* p : {(void*)l0, (void*)l1, (void*)w[0], (void*)w[1], (void*)ctl, (void*)token}) sycl::free(p, q);
    return r;
  }
};

template <class T> static Result host_split(const std::vector<T>& x, uint32_t r0, uint32_t* records) {
  draft_split::shard(x.data(), r0, 0, records);
  draft_split::shard(x.data() + r0, uint32_t(x.size()) - r0, r0, records + 4);
  int32_t t = -7; const bool ok = draft_split::merge(records, records + 4, t);
  return {ok ? t : -7, !ok};
}

static int failures = 0, cases = 0, ties_across = 0, negative_detected = 0;
template <class T> static void check(Device& d, const std::string& name, const std::vector<T>& x, uint32_t r0, uint32_t base, uint32_t words, bool expect_fail, int expect_index = -1) {
  ++cases;
  const Result a = ref(x), b = d.fast(x); uint32_t dev_records[8], host_records[8]; int token1 = -7;
  const Result c = d.split(x, r0, base, words, false, false, dev_records, &token1), h = host_split(x, r0, host_records);
  bool ok = a.fail == expect_fail && b.fail == expect_fail && c.fail == expect_fail && h.fail == expect_fail;
  if (!expect_fail) ok = ok && a.index == b.index && a.index == c.index && a.index == h.index && token1 == c.index && (expect_index < 0 || a.index == expect_index);
  else ok = ok && token1 == -7;  // both cards fail and leave next_token untouched
  for (int i = 0; i < 8; ++i) ok = ok && dev_records[i] == host_records[i];
  if (!expect_fail) {
    const float m = draft_split::logit_value(x[a.index]); bool lo = false, hi = false;
    for (size_t j = 0; j < x.size(); ++j) if (draft_split::logit_value(x[j]) == m) (j < r0 ? lo : hi) = true;
    ties_across += lo && hi;
    const int wrong = draft_split::bits_value(host_records[4]) >= draft_split::bits_value(host_records[0]) ? int(host_records[5]) : int(host_records[1]);
    negative_detected += wrong != a.index;
  }
  if (!ok) { ++failures; std::printf("FAIL %s r0=%u: ref %d/%d fast %d/%d split %d/%d (card 1 %d) host %d/%d expect %d fail %d\n", name.c_str(), r0,
    a.index, a.fail, b.index, b.fail, c.index, c.fail, token1, h.index, h.fail, expect_index, expect_fail); }
}

template <class T> static void suite(Device& d, const char* label, uint32_t R, std::vector<uint32_t> splits, uint32_t base, uint32_t words, std::mt19937& rng) {
  auto randoms = [&](size_t n, float scale) { std::normal_distribution<float> nd(0.f, scale); std::vector<T> v(n); for (auto& e : v) e = from_float<T>(nd(rng)); return v; };
  const std::string L = label;
  for (int t = 0; t < 12; ++t) for (uint32_t r0 : splits) check(d, L + " random" + std::to_string(t), randoms(R, t % 2 ? 1.f : 6.f), r0, base, words, false);
  for (uint32_t r0 : splits) {
    auto x = randoms(R, 1.f); const T top = from_float<T>(64.f);
    const uint32_t r1 = R - r0, a1 = r1 / 3, b1 = 2 * r1 / 3;
    { auto y = x; y[7] = top; y[r0 + a1] = top; check(d, L + " equal max across split", y, r0, base, words, false, 7); }
    { auto y = x; y[r0 - 1] = top; y[r0] = top; check(d, L + " equal max at the boundary", y, r0, base, words, false, int(r0 - 1)); }
    { auto y = x; y[r0 + a1] = top; y[r0 + b1] = top; check(d, L + " equal max inside card 1", y, r0, base, words, false, int(r0 + a1)); }
    { auto y = x; y[r0 + b1] = top; check(d, L + " max only on card 1", y, r0, base, words, false, int(r0 + b1)); }
    { auto y = x; y[3] = top; y[1027] = top; y[r0 + a1] = top; check(d, L + " equal max in two lanes and card 1", y, r0, base, words, false, 3); }
    { std::vector<T> y(R, from_float<T>(1.f)); check(d, L + " all equal", y, r0, base, words, false, 0); }
    if constexpr (std::is_same_v<T, float>) {  // F32-only edge values
      { auto y = x; y[r0 + a1] = FLT_MAX; y[5] = FLT_MAX; check(d, L + " FLT_MAX on both cards", y, r0, base, words, false, 5); }
      { std::vector<T> y(R, -FLT_MAX); y[r0 + b1] = std::nextafter(-FLT_MAX, 0.f); check(d, L + " all -FLT_MAX but one on card 1", y, r0, base, words, false, int(r0 + b1)); }
      { std::vector<T> y(R, -1.f); y[r0 + a1] = FLT_TRUE_MIN; y[9] = FLT_TRUE_MIN; check(d, L + " equal denormal maxima across split", y, r0, base, words, false, 9); }
      { std::vector<T> y(R, -1.f); y[9] = FLT_TRUE_MIN; y[r0 + a1] = 2 * FLT_TRUE_MIN; check(d, L + " larger denormal on card 1", y, r0, base, words, false, int(r0 + a1)); }
      { auto y = x; y[11] = std::nextafter(64.f, 0.f); y[r0 + a1] = 64.f; check(d, L + " one ulp larger on card 1", y, r0, base, words, false, int(r0 + a1)); }
    }
    std::vector<T> neg(R); for (auto& e : neg) e = from_float<T>(-(1.f + std::abs(std::normal_distribution<float>(0, 1)(rng))));
    { auto y = neg; y[11] = from_bits<T>(0x80000000u); y[r0 + a1] = from_float<T>(0.f); check(d, L + " -0 on card 0, +0 on card 1", y, r0, base, words, false, 11); }
    { auto y = neg; y[11] = from_float<T>(0.f); y[r0 + a1] = from_bits<T>(0x80000000u); check(d, L + " +0 on card 0, -0 on card 1", y, r0, base, words, false, 11); }
    { auto y = neg; y[r0 + a1] = from_bits<T>(0x80000000u); y[r0 + b1] = from_float<T>(0.f); check(d, L + " -0 then +0 on card 1", y, r0, base, words, false, int(r0 + a1)); }
    { auto y = neg; y[r0 + a1] = from_float<T>(0.f); y[r0 + b1] = from_bits<T>(0x80000000u); check(d, L + " +0 then -0 on card 1", y, r0, base, words, false, int(r0 + a1)); }
    { auto y = neg; y[2048] = from_bits<T>(0x80000000u); y[1024] = from_float<T>(0.f); check(d, L + " +0 and -0 in one lane on card 0", y, r0, base, words, false, 1024); }
    for (uint32_t bits : {0x7fc00000u, 0x7f800000u, 0xff800000u, 0xffc00001u}) {
      { auto y = x; y[5] = from_bits<T>(bits); check(d, L + " non-finite on card 0", y, r0, base, words, true); }
      { auto y = x; y[r0 + b1] = from_bits<T>(bits); check(d, L + " non-finite on card 1", y, r0, base, words, true); }
      { auto y = x; y[R - 1] = from_bits<T>(bits); y[0] = from_bits<T>(bits); check(d, L + " non-finite on both cards", y, r0, base, words, true); }
    }
  }
  int preset_ok = 0;  // a sticky error already set on card 0 or card 1: the merge fails, next_token untouched
  for (int which = 0; which < 2; ++which) { auto x = randoms(R, 1.f); int t1 = -7;
    const Result r = d.split(x, splits[0], base, words, which == 0, which == 1, nullptr, &t1);
    preset_ok += (which == 0 ? r.fail && r.index == -7 : r.fail && r.index == -7); }
  ++cases; if (preset_ok != 2) { ++failures; std::printf("FAIL %s preset sticky error cases %d/2\n", label, preset_ok); }
}

int main() {
  Device d;
  std::printf("device: %s\n", d.q.get_device().get_info<sycl::info::device::name>().c_str());
  std::mt19937 rng(20261029);
  suite<float>(d, "target-f32", 248320, {124160, 128, 248192, 1024, 131072, 117248}, 0, 8, rng);
  const int target_cases = cases, target_ties = ties_across;
  suite<u16>(d, "draft-bf16", 91392, {45824, 128, 91264, 46080}, draft_split::records, draft_split::words, rng);
  std::printf("cases %d (target F32 %d, draft BF16 %d), failures %d, cases with the maximum on both cards %d (target %d)\n",
              cases, target_cases, cases - target_cases, failures, ties_across, target_ties);
  std::printf("negative control (card 1 wins ties): differs from ArgmaxFast in %d cases (must be > 0)\n", negative_detected);
  if (!negative_detected) ++failures;
  std::printf("%s\n", failures ? "FAIL" : "PASS");
  return failures ? 1 : 0;
}
