#include "stage2/packet194-expert-diet-engine/host_spin.hpp"
#ifndef P56X_SLEEP20
#error "A sealed wait policy is required"
#endif
static_assert(P56X_SLEEP20 == 0 || P56X_SLEEP20 == 1);
namespace p56x { const bool sleep20 = P56X_SLEEP20; }
