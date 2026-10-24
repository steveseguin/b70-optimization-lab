#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/owner_api.hpp"
namespace ownrt {
void set_stop_channel(int fd);
struct CopyAudit { uint64_t host_to_device[2]{},device_to_host[2]{},peer[2]{},device_local[2]{}; };
CopyAudit copy_audit(const Device&);
}
