#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet35-hostpath/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet35-hostpath/owner.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet35-hostpath/build/checked/experiments/own-xpu-runtime/stage2/packet35-hostpath/owner_api.hpp"
namespace ownrt {
struct CopyAudit { uint64_t host_to_device[2]{},device_to_host[2]{},peer[2]{},device_local[2]{}; };
CopyAudit copy_audit(const Device&);
}
