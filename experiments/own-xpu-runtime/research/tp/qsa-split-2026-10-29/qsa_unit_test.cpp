// CPU unit test of the exact QSA split by KV group (OWNRT_TP_QSA_SPLIT=1, ng::qsa_group_flag, 2026-10-29).
// Card c owns KV head c and query heads [12c, 12c+12). Each parameterized kernel run on a card's compact half must
// reproduce, bitwise, the full-geometry kernel's results for that card's heads; the replicated parts (index query,
// raw and pooled index keys) must equal the full run's. F32 exact mode throughout (as the service runs).
//   (1) generic prepare and pool (ng::group through ng::cpu, the host twin of the generic device kernel);
//   (2) generic attention score/softmax/value (ng::cpu);
//   (3) the production attention passes, p47::admit_fast + tiles_heads + combine_blocked (F32), run as SYCL kernels
//       on the OpenCL CPU device: outputs and every valid partial (258 floats per row, head and tile);
//   (4) p47ref::cpu_split (the host-only build's twin).
// Negative control: card 1 reading KV head 0 must differ.
// No GPU is opened:
//   source /opt/intel/oneapi/setvars.sh
//   icpx -fsycl -std=gnu++20 -O1 -fno-fast-math -ffp-contract=off -I ../../../engine/src qsa_unit_test.cpp -o /dev/shm/qsa_unit_test
//   ONEAPI_DEVICE_SELECTOR=opencl:cpu /dev/shm/qsa_unit_test
#include "stage2/packet194-expert-diet-engine/p49_qsa_kernel.hpp"
#include "stage2/packet194-expert-diet-engine/p49_qsa_reference.hpp"
#include <cstdio>
#include <cstring>
#include <numeric>
#include <random>
#include <string>
#include <vector>

std::uint64_t ownrt::next_handle() { static std::uint64_t n = 0; return ++n; }

constexpr int QH = 24, KVH = 2, AD = 256, ID = 128, S = 2051;
using Buf = std::vector<float>;
static int failures = 0, checks = 0, controls = 0;
static void expect(bool ok, const std::string& what) { ++checks; if (!ok) { ++failures; std::printf("FAIL %s\n", what.c_str()); } }
static bool same(const float* a, const float* b, size_t n) { return std::memcmp(a, b, n * 4) == 0; }

struct Slots {  // 19 bound slots as F32/I32 words
  std::array<std::vector<uint32_t>, 19> d;
  ng::Args args() { ng::Args a; for (int j = 0; j < 19; ++j) a.p[j] = d[j].data(); a.f32 = true; return a; }
  float* f(int j) { return reinterpret_cast<float*>(d[j].data()); }
  int32_t* i(int j) { return reinterpret_cast<int32_t*>(d[j].data()); }
};
static void size_slots(Slots& s, ng::Shape sh) { auto n = ng::required_bytes(sh); for (int j = 0; j < 19; ++j) s.d[j].assign((n[j] + 3) / 4 + 16, 0); }
static float rnd(std::mt19937& g, int pattern) {
  if (pattern == 1) return (g() & 1) ? -0.f : 0.f;
  if (pattern == 2) return float(int(g() % 17) - 8) * 4.f;
  return float(int(g() % 2047) - 1023) / 1024.f;
}
static void fill(std::vector<uint32_t>& v, size_t n, std::mt19937& g, int pattern = 0) { for (size_t j = 0; j < n; ++j) { float x = rnd(g, pattern); std::memcpy(&v[j], &x, 4); } }
static ng::Shape split(ng::Shape s) { s.flags |= ng::qsa_group_flag; s.heads = 12; return s; }

// ---- (1) prepare ----
static void test_prepare(int T, int pos, uint32_t seed) {
  std::mt19937 g(seed);
  ng::Shape full{ng::prepare, T, 2560, 4, 0, ng::f32_activations_flag | 8, 4096, 2048};
  Slots F; size_slots(F, full);
  fill(F.d[0], size_t(T) * QH * 512, g); fill(F.d[1], size_t(T) * KVH * AD, g); fill(F.d[2], size_t(T) * 4 * ID, g);
  fill(F.d[3], 256, g); fill(F.d[4], 256, g); fill(F.d[5], 128, g); fill(F.d[16], size_t(full.capacity) * 64, g);
  F.i(15)[0] = 0; F.i(17)[0] = pos; F.i(18)[0] = 1;
  Slots H[2];
  for (int c = 0; c < 2; ++c) {
    auto hs = split(full); size_slots(H[c], hs);
    for (int r = 0; r < T; ++r) {
      std::memcpy(H[c].f(0) + size_t(r) * 12 * 512, F.f(0) + size_t(r) * QH * 512 + size_t(c) * 12 * 512, 12 * 512 * 4);
      std::memcpy(H[c].f(1) + size_t(r) * AD, F.f(1) + size_t(r) * KVH * AD + size_t(c) * AD, AD * 4);
    }
    for (int j : {2, 3, 4, 5, 16}) H[c].d[j] = F.d[j];
    H[c].i(15)[0] = 0; H[c].i(17)[0] = pos; H[c].i(18)[0] = 1;
    ng::cpu(hs, H[c].args());
  }
  ng::cpu(full, F.args());
  for (int c = 0; c < 2; ++c) for (int r = 0; r < T; ++r) {
    expect(same(H[c].f(6) + size_t(r) * 12 * AD, F.f(6) + size_t(r) * QH * AD + size_t(c) * 12 * AD, 12 * AD), "prepare q");
    expect(same(H[c].f(7) + size_t(r) * 12 * AD, F.f(7) + size_t(r) * QH * AD + size_t(c) * 12 * AD, 12 * AD), "prepare gate");
    expect(same(H[c].f(8) + size_t(r) * AD, F.f(8) + size_t(r) * KVH * AD + size_t(c) * AD, AD), "prepare kn");
    expect(same(H[c].f(9) + size_t(r) * 4 * ID, F.f(9) + size_t(r) * 4 * ID, 4 * ID), "prepare index q (replicated)");
  }
  expect(F.i(15)[0] == 0 && H[0].i(15)[0] == 0 && H[1].i(15)[0] == 0, "prepare error clear");
}

// ---- (1) pool ----
static void test_pool(int T, int pos, int C, uint32_t seed) {
  std::mt19937 g(seed);
  ng::Shape full{ng::pool, T, 2560, 4, 0, ng::f32_activations_flag | 8, C, 2048};
  Slots F; size_slots(F, full);
  fill(F.d[0], size_t(T) * KVH * AD, g); fill(F.d[1], size_t(T) * KVH * AD, g); fill(F.d[2], size_t(T) * ID, g); fill(F.d[3], 128, g);
  fill(F.d[4], size_t(C) * KVH * AD, g); fill(F.d[5], size_t(C) * KVH * AD, g); fill(F.d[6], size_t(C) * ID, g); fill(F.d[7], size_t((C + 3) / 4) * ID, g);
  fill(F.d[16], size_t(C) * 64, g);
  F.i(15)[0] = 0; F.i(17)[0] = pos; F.i(18)[0] = 1;
  Slots H[2];
  for (int c = 0; c < 2; ++c) {
    auto hs = split(full); size_slots(H[c], hs);
    for (int r = 0; r < T; ++r) for (int j : {0, 1}) std::memcpy(H[c].f(j) + size_t(r) * AD, F.f(j) + size_t(r) * KVH * AD + size_t(c) * AD, AD * 4);
    for (int p = 0; p < C; ++p) for (int j : {4, 5}) std::memcpy(H[c].f(j) + size_t(p) * AD, F.f(j) + size_t(p) * KVH * AD + size_t(c) * AD, AD * 4);
    for (int j : {2, 3, 6, 7, 16}) H[c].d[j] = F.d[j];
    H[c].i(15)[0] = 0; H[c].i(17)[0] = pos; H[c].i(18)[0] = 1;
    ng::cpu(hs, H[c].args());
  }
  ng::cpu(full, F.args());
  for (int c = 0; c < 2; ++c) {
    bool kv = true;
    for (int p = 0; p < C; ++p) for (int j : {4, 5}) kv = kv && same(H[c].f(j) + size_t(p) * AD, F.f(j) + size_t(p) * KVH * AD + size_t(c) * AD, AD);
    expect(kv, "pool keys/values (every position)");
    expect(same(H[c].f(6), F.f(6), size_t(C) * ID) && same(H[c].f(7), F.f(7), size_t((C + 3) / 4) * ID), "pool raw/pooled (replicated)");
  }
}

// ---- attention fixture: F32 q, gate, keys, values and selected ids (as p47ref::Fixture, F32) ----
struct Att {
  ng::Shape full; Slots F; int T;
  Att(int C, int T_, uint32_t seed, int pattern) : full{ng::attention_score, T_, 2560, 4, 0, ng::f32_activations_flag, C, 2048}, T(T_) {
    std::mt19937 g(seed); size_slots(F, full);
    fill(F.d[0], size_t(T) * QH * AD, g, pattern); fill(F.d[1], size_t(T) * QH * AD, g);
    fill(F.d[2], size_t(C) * KVH * AD, g, pattern); fill(F.d[3], size_t(C) * KVH * AD, g, pattern == 1 ? 1 : 0);
    std::fill_n(F.i(4), size_t(T) * S, -1);
    for (int r = 0; r < T; ++r) {
      int occupied = C - T + r + 1, blocks = occupied / 4; std::vector<int> ids(blocks); std::iota(ids.begin(), ids.end(), 0);
      for (int i = blocks - 1; i > 0; --i) std::swap(ids[i], ids[g() % uint32_t(i + 1)]);
      int at = 0; for (int j = 0; j < std::min(blocks, 512); ++j) for (int d = 0; d < 4; ++d) F.i(4)[r * S + at++] = ids[j] * 4 + d;
      for (int j = blocks * 4; j < occupied; ++j) F.i(4)[r * S + at++] = j;
    }
    F.i(15)[0] = 0; F.i(17)[0] = C - T; F.i(18)[0] = 1;
  }
  Slots half(int c, int kv_from) {  // kv_from: the KV head this half reads (c, or the wrong one for the negative control)
    auto hs = split(full); Slots H; size_slots(H, hs);
    for (int r = 0; r < T; ++r) for (int j : {0, 1}) std::memcpy(H.f(j) + size_t(r) * 12 * AD, F.f(j) + size_t(r) * QH * AD + size_t(c) * 12 * AD, 12 * AD * 4);
    for (int p = 0; p < full.capacity; ++p) for (int j : {2, 3}) std::memcpy(H.f(j) + size_t(p) * AD, F.f(j) + size_t(p) * KVH * AD + size_t(kv_from) * AD, AD * 4);
    H.d[4] = F.d[4]; H.i(15)[0] = 0; H.i(17)[0] = F.i(17)[0]; H.i(18)[0] = 1; return H;
  }
};

// ---- (2) generic attention and (4) cpu_split ----
static void test_attention_host(Att& A, const std::string& tag) {
  Slots F = A.F; ng::cpu(A.full, F.args()); { ng::Shape s = A.full; s.op = ng::attention_softmax; ng::cpu(s, F.args()); s.op = ng::attention_value; ng::cpu(s, F.args()); }
  const bool ref = A.T <= 2;  // cpu_split admits decode geometry (1-2 rows)
  Slots R = A.F; if (ref) p47ref::cpu_split(A.full, R.args());
  for (int c = 0; c < 2; ++c) {
    auto hs = split(A.full);
    Slots H = A.half(c, c); ng::cpu(hs, H.args()); { ng::Shape s = hs; s.op = ng::attention_softmax; ng::cpu(s, H.args()); s.op = ng::attention_value; ng::cpu(s, H.args()); }
    Slots HR = A.half(c, c); if (ref) p47ref::cpu_split(hs, HR.args());
    for (int r = 0; r < A.T; ++r) {
      expect(same(H.f(5) + size_t(r) * 12 * AD, F.f(5) + size_t(r) * QH * AD + size_t(c) * 12 * AD, 12 * AD), "generic attention y " + tag);
      expect(same(H.f(7) + size_t(r) * 12 * S, F.f(7) + size_t(r) * QH * S + size_t(c) * 12 * S, 12 * S), "generic attention probabilities " + tag);
      if (ref) expect(same(HR.f(5) + size_t(r) * 12 * AD, R.f(5) + size_t(r) * QH * AD + size_t(c) * 12 * AD, 12 * AD), "cpu_split y " + tag);
    }
  }
}

// ---- (3) production device passes on the OpenCL CPU device ----
struct Dev {
  sycl::queue q{sycl::cpu_selector_v, sycl::property::queue::in_order{}};
  struct Out { Buf y; Buf partial; std::vector<int> counts; int error; };
  Out run(ng::Shape s, Slots& in, bool fast_admit = true) {
    auto n = ng::required_bytes(s);
    std::array<void*, 19> p{};
    for (int j = 0; j < 19; ++j) { size_t bytes = std::max<size_t>(n[j], 64); p[j] = sycl::malloc_shared(bytes, q); std::memset(p[j], 0, bytes); std::memcpy(p[j], in.d[j].data(), std::min(bytes, in.d[j].size() * 4)); }
    ng::Args a; for (int j = 0; j < 19; ++j) a.p[j] = p[j]; a.f32 = true;
    const size_t partial_floats = p47::scratch_floats(s);
    int* counts = sycl::malloc_shared<int>(4, q); float* partial = sycl::malloc_shared<float>(partial_floats + 16, q);
    std::fill_n(partial, partial_floats + 16, std::bit_cast<float>(0x7fc00001u)); std::fill_n(counts, 4, -7);
    auto e0 = fast_admit ? p47::admit_fast(q, s, a, counts) : p47::admit(q, s, a, counts);
    auto e1 = p47::tiles_heads<true>(q, s, a, counts, partial, {e0});
    p47::combine_blocked<true>(q, s, a, counts, partial, {e1}).wait();
    Out o; const int QHs = ng::qsa_query_heads(s);
    o.y.assign(static_cast<float*>(p[5]), static_cast<float*>(p[5]) + size_t(s.tokens) * QHs * AD);
    o.partial.assign(partial, partial + partial_floats); o.counts.assign(counts, counts + s.tokens); o.error = static_cast<int*>(p[15])[0];
    for (auto x : p) sycl::free(x, q); sycl::free(counts, q); sycl::free(partial, q);
    return o;
  }
};
static void test_attention_device(Dev& D, Att& A, const std::string& tag, bool control) {
  auto F = D.run(A.full, A.F);
  const int C = p47::splits(A.full);
  int differ = 0;
  for (int c = 0; c < 2; ++c) {
    auto hs = split(A.full); Slots in = A.half(c, c); auto H = D.run(hs, in, c == 0);  // card 1 with the single-item admit
    expect(H.error == 0 && F.error == 0, "device attention error clear " + tag);
    expect(H.counts == F.counts, "device admit counts " + tag);
    for (int r = 0; r < A.T; ++r) {
      expect(same(H.y.data() + size_t(r) * 12 * AD, F.y.data() + size_t(r) * QH * AD + size_t(c) * 12 * AD, 12 * AD), "device attention y " + tag);
      const int tiles = (F.counts[r] + 31) / 32;
      bool parts = true;
      for (int h = 0; h < 12; ++h) for (int t = 0; t < tiles; ++t)
        parts = parts && same(H.partial.data() + (size_t(r * 12 + h) * C + t) * 258, F.partial.data() + (size_t(r * QH + c * 12 + h) * C + t) * 258, 258);
      expect(parts, "device attention partials " + tag);
    }
    if (c == 1 && control) {  // negative control: card 1's heads over KV head 0 (not for all-zero K/V, pattern 1)
      Slots wrong = A.half(1, 0); auto W = D.run(hs, wrong);
      for (int r = 0; r < A.T; ++r) differ += !same(W.y.data() + size_t(r) * 12 * AD, F.y.data() + size_t(r) * QH * AD + 12 * AD, 12 * AD);
    }
  }
  if (control) { expect(differ == A.T, "negative control differs " + tag); ++controls; }
}

int main() {
  // (1)
  for (int T : {1, 2, 4, 7}) for (int pos : {0, 3, 30, 31, 4093}) test_prepare(T, std::min(pos, 4096 - T), 11u + T * 37u + pos);
  for (int T : {1, 2, 4, 5}) for (int pos : {0, 1, 3, 4, 7, 61, 123}) test_pool(T, pos, 128, 101u + T * 13u + pos);
  test_pool(256, 512, 1024, 777u);  // a 256-row prefill chunk
  const int prep_pool = checks;
  // (2)-(4)
  Dev D; std::printf("device: %s\n", D.q.get_device().get_info<sycl::info::device::name>().c_str());
  int cases = 0;
  for (int n : {1, 2, 31, 32, 33, 63, 64, 65, 100, 300, 513, 1025, 2047, 2048, 2049, 2050, 2051, 3000})
    for (int T : {1, 2, 4}) for (int pattern : {0, 1, 2}) {
      if (pattern && T != 1 && n != 65 && n != 2051) continue;
      if (n < T) continue;
      Att A(n, T, 1000u + n * 7u + T * 3u + pattern, pattern);
      const std::string tag = "n=" + std::to_string(n) + " T=" + std::to_string(T) + " pattern=" + std::to_string(pattern);
      if (n <= 1025 || pattern == 0) test_attention_host(A, tag);
      test_attention_device(D, A, tag, pattern != 1); ++cases;
    }
  std::printf("prepare/pool checks %d; attention cases %d (negative controls %d, each differs); checks %d; failures %d\n", prep_pool, cases, controls, checks, failures);
  std::printf(failures ? "FAIL\n" : "PASS\n");
  return failures != 0;
}
