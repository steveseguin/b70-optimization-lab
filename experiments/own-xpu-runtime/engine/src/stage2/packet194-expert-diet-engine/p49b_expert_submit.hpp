#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/p39_submit.hpp"
#include "stage2/packet194-expert-diet-engine/p49b_gemv.hpp"
namespace p49b {
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,p39::Kind,const p39::Bindings&);
}
