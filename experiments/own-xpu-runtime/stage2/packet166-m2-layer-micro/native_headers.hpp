#pragma once
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/kernel_guard.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p42_cooperative.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p60_kernels.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p73_hc.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p82b_recurrence.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49_qsa_reference.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p109_fusion.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p100_down.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p90_expert.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p42_tiny.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/round2.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/batched_rows.hpp"
#include "native/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/batched_experts.hpp"

#ifndef OWN_RT_HOST_ONLY
#include "native/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49_qsa_kernel.hpp"
#endif
