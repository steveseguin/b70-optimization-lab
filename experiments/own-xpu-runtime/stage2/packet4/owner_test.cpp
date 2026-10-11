#include "mock_device.hpp"
#include "owner.hpp"
#include <iostream>
using namespace ownrt;
static void check(bool b) {
  if (!b)
    throw std::runtime_error("owner retirement test");
}
int main() {
  auto b = std::make_unique<MockDevice>();
  auto *mock = b.get();
  Device d(std::move(b));
  auto a = d.arena.allocate("a", 4, Memory::pinned, Category::pinned_slab,
                            Lifetime::transfer);
  auto z = d.arena.allocate("z", 4, Memory::device, Category::weights,
                            Lifetime::process);
  CopyEngine copy(d);
  auto e = copy.copy(z, 0, a, 0, 4, {});
  bool caught = false;
  try {
    d.retire_completed_events();
  } catch (const std::logic_error &) {
    caught = true;
  }
  check(caught);
  mock->finish(e);
  d.retire_completed_events();
  caught = false;
  try {
    d.wait(e, std::chrono::milliseconds(1));
  } catch (const std::invalid_argument &) {
    caught = true;
  }
  check(caught);
  for (int i = 0; i < 5000; ++i) {
    auto next = copy.copy(z, 0, a, 0, 4, {});
    mock->finish(next);
    d.retire_completed_events();
  }
  d.graph("lease", {z}, [] {});
  caught = false;
  try {
    d.retire_completed_events();
  } catch (const std::logic_error &) {
    caught = true;
  }
  check(caught);
  check(d.shutdown(std::chrono::milliseconds(10)).safe_to_exit);
  std::cout << "4 owner retirement cases PASS\n";
}
