#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/lifetime_test.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/build/checked/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/lifetime_mock.hpp"
#include <cassert>
#include <functional>
#include <iostream>
int main() {
  using namespace packet18;
  for(auto kind:{"kernel-bundle","kernel","event","queue","context","lambda-capture"}) {
    auto state=std::make_shared<ContextOrder>();
    {
      auto ref=std::make_shared<ContextReference>(state,kind);
      std::function<void()> capture=[ref]{};
      ref.reset();state->release_native();
    }
    assert(!state->passed() && state->late_destructions==1);
    assert(state->order.front()=="native-context-release");
  }
  auto state=std::make_shared<ContextOrder>();
  try {auto ref=std::make_shared<ContextReference>(state,"kernel-bundle");throw 1;}
  catch(int) {state->release_native();}
  assert(state->passed() && state->order.back()=="native-context-release");
  std::cout<<"7/7 context lifetime controls pass (six late-destruction detections, exception unwind)\n";
}
