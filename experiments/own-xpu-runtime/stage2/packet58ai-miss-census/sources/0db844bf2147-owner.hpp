#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/3a8ce69382d2-kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/8ba8ab46fbd1-owner_api.hpp"
namespace ownrt {
void set_stop_channel(int fd);
struct CopyAudit { uint64_t host_to_device[2]{},device_to_host[2]{},peer[2]{},device_local[2]{}; };
CopyAudit copy_audit(const Device&);
}
