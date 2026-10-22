#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/owner.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/owner_api.hpp"
namespace ownrt {
void set_stop_channel(int fd);
struct CopyAudit { uint64_t host_to_device[2]{},device_to_host[2]{},peer[2]{},device_local[2]{}; };
CopyAudit copy_audit(const Device&);
}
