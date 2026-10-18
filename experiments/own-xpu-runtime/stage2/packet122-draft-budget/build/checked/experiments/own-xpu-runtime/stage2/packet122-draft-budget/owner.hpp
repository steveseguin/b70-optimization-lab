#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/owner.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/build/checked/experiments/own-xpu-runtime/stage2/packet122-draft-budget/owner_api.hpp"
namespace ownrt {
void set_stop_channel(int fd);
struct CopyAudit { uint64_t host_to_device[2]{},device_to_host[2]{},peer[2]{},device_local[2]{}; };
CopyAudit copy_audit(const Device&);
}
