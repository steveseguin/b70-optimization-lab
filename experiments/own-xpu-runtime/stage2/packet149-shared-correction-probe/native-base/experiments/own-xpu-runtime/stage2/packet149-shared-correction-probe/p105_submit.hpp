#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p105_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/build/checked/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/p105_common.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/build/checked/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/performance.hpp"
namespace p105 {
ownrt::Event pack(ownrt::Device&,ownrt::Allocation logits,ownrt::Allocation index,ownrt::Allocation error,ownrt::Allocation best,unsigned rows,unsigned offset);
}
