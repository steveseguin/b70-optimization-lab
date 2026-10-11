#include "../kernels/mock.hpp"
#include "../step/plan.hpp"
#include <cstring>
#include <iostream>
#include <limits>
using namespace flash;
using namespace flash::mock;
static void check(bool p) {
  if (!p)
    throw std::runtime_error("check failed");
}
static Launch named(const Plan &p, const std::string &op) {
  for (auto &l : p.launches)
    if (l.op == op)
      return l;
  throw std::runtime_error("no op");
}
int main() {
  int passed = 0;
  auto test = [&](const char *name, auto f) {
    try {
      f();
      ++passed;
      std::cout << name << " PASS\n";
    } catch (const std::exception &e) {
      std::cerr << name << ": " << e.what() << '\n';
      throw;
    }
  };
  auto p = Builder(Geometry::tiny()).build({false, true});
  test("bf16_ties_even_signed_zero", [] {
    check(std::bit_cast<uint32_t>(bf(-0.f)) == 0x80000000u);
    check(bf(iq3::bits_float(0x3f808000)) == 1.f);
    check(std::bit_cast<uint32_t>(bf(iq3::bits_float(0x3f818000))) ==
          0x3f820000);
  });
  test("odd_tree_fixed_order", [] {
    check(tree({1e20f, -1e20f, 3.f}) == 3.f);
    check(tree({1e20f, 3.f, -1e20f}) == 0.f);
  });
  test("gdn_dot_contiguous_four", [] {
    V a(128, 1), b(128, 0);
    b[0] = 1e20f;
    b[1] = 3;
    b[2] = -1e20f;
    b[3] = 4;
    check(dot(a, b, true) == 4);
  });
  test("packet2_gemv_order", [] {
    const std::string name = "fixture";
    V x(65);
    for (int k = 0; k < 65; ++k)
      x[k] = bf(float(k % 9 - 4) / 16);
    std::vector<uint16_t> bits;
    for (float v : x)
      bits.push_back(iq3::bf16_bits(v));
    std::vector<uint8_t> packed(65 * 4);
    for (int k = 0; k < 65; ++k) {
      float v = weight(name, 0, k);
      std::memcpy(packed.data() + 4 * k, &v, 4);
    }
    check(linear(x, 1, 65, name)[0] ==
          bf(iq3::gemv_row(Type::F32, packed.data(), bits.data(), Type::BF16,
                           65)));
  });
  test("gdn_sigmoid_zero_gate", [&] {
    Cpu c(p);
    auto l = named(p, "gdn_norm_gate");
    c.data[l.inputs[0]] = V(12, 1.f);
    c.data[l.inputs[1]] = V(12, 0.f);
    c.enqueue(l, 0);
    check(std::any_of(c.data[l.outputs[0]].begin(), c.data[l.outputs[0]].end(),
                      [](float x) { return x != 0.f; }));
  });
  test("route_lowest_id_ties", [&] {
    Cpu c(p);
    auto l = named(p, "route");
    c.data[l.inputs[0]] = V(16, 0);
    c.enqueue(l, 0);
    for (int i = 0; i < 10; ++i)
      check(c.data[l.outputs[0]][i] == i);
    for (float v : c.data[l.outputs[1]])
      check(v == .1f);
  });
  test("route_nonfinite_rejected", [&] {
    Cpu c(p);
    auto l = named(p, "route");
    c.data[l.inputs[0]][0] = std::numeric_limits<float>::quiet_NaN();
    bool caught = false;
    try {
      c.enqueue(l, 0);
    } catch (...) {
      caught = true;
    }
    check(caught);
  });
  test("argmax_zero_tie_and_sticky_error", [&] {
    Cpu c(p);
    auto l = named(p, "argmax");
    c.data["logits"] = V(16, -1);
    c.data["logits"][2] = -0.f;
    c.data["logits"][7] = 0;
    c.data["error"] = {1};
    c.enqueue(l, 0);
    check(c.data["next_token"][0] == 2);
    check(c.data["error"][0] == 1);
  });
  test("argmax_nan_forbids_commit", [&] {
    Cpu c(p);
    auto l = named(p, "argmax");
    c.enqueue(p.launches[0], 0);
    c.data["logits"][4] = std::numeric_limits<float>::quiet_NaN();
    c.enqueue(l, c.last());
    c.enqueue(p.launches.back(), c.last());
    check(c.data["position"][0] == 0);
    check(c.data["error"][0] == 1);
  });
  test("changed_token_changes_state", [&] {
    Cpu a(p), b(p);
    a.data["token"] = {2};
    b.data["token"] = {3};
    p.execute(a, 0);
    p.execute(b, 0);
    check(a.data["streams"] != b.data["streams"]);
    check(a.data["blk.0.gdn.state"] != b.data["blk.0.gdn.state"]);
  });
  test("changed_state_changes_output", [&] {
    Cpu a(p), b(p);
    b.data["blk.0.gdn.state"] = V(48, .5f);
    p.execute(a, 0);
    p.execute(b, 0);
    check(a.data["blk.0.gdn.y"] != b.data["blk.0.gdn.y"]);
  });
  test("inactive_does_not_advance", [&] {
    Cpu c(p);
    c.data["active"] = {0};
    auto before = c.data;
    p.execute(c, 0);
    check(c.data == before);
  });
  test("submission_failure_rolls_back", [&] {
    auto broken = p;
    auto it = std::find_if(broken.launches.begin(), broken.launches.end(),
                           [](auto &l) { return l.op == "route"; });
    it->op = "injected_failure";
    Cpu c(p);
    auto before = c.data;
    bool caught = false;
    try {
      broken.execute(c, 0);
    } catch (...) {
      caught = true;
    }
    check(caught && c.data == before);
    p.execute(c, c.last());
    Cpu fresh(p);
    p.execute(fresh, 0);
    check(c.data == fresh.data);
  });
  test("context_exhaustion_no_mutation", [&] {
    Cpu c(p);
    c.data["position"] = {8};
    auto before = c.data;
    bool caught = false;
    try {
      p.execute(c, 0);
    } catch (...) {
      caught = true;
    }
    check(caught && c.data == before);
  });
  test("replay_from_checkpoint_exact", [&] {
    Cpu a(p), b(p);
    for (int id : {2, 5, 3, 7, 1}) {
      a.data["token"] = {float(id)};
      b.data["token"] = {float(id)};
      p.execute(a, a.last());
      p.execute(b, b.last());
    }
    check(a.data == b.data);
    check(a.data["position"][0] == 5);
    for (float v : a.data["blk.0.gdn.state"])
      check((std::bit_cast<uint32_t>(v) & 65535) == 0);
  });
  test("dependency_chain_required", [&] {
    Cpu c(p);
    p.execute(c, 0);
    auto before = c.data;
    bool caught = false;
    try {
      p.execute(c, c.last() + 1);
    } catch (...) {
      caught = true;
    }
    check(caught && c.data == before);
  });
  test("mtp_absent_fails_closed", [] {
    bool caught = false;
    try {
      Builder(Geometry::tiny()).build({false, true}, false, true);
    } catch (const std::invalid_argument &) {
      caught = true;
    }
    check(caught);
  });
  test("ple_dilation_nine_rows", [&] {
    Cpu c(p);
    auto l = named(p, "ple_hash");
    check(l.inputs[2] == "ple_metadata");
    check(c.data["blk.1.ple.history"].size() == 4 * 16 * 9);
  });
  std::cout << "passed " << passed << '\n';
}
