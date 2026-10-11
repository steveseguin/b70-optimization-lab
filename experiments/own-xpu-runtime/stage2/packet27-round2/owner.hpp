#pragma once
// API unchanged; packet-local owner.cpp supplies chained execution policy.
#include "../../stage1/packet3-prep/src/owner.hpp"

namespace ownrt {
struct CopyAudit { uint64_t host_to_device[2]{},device_to_host[2]{},peer[2]{},device_local[2]{}; };
CopyAudit copy_audit(const Device&);
}
