#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p28/submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p28/registry.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p58_pointer.hpp"
namespace p28 {
struct Bound {
 const uint8_t* w{};const uint8_t* peer{};const uint16_t* x{};uint16_t* y{};uint16_t* py{};
 const iq3::Route* routes{};uint32_t* status{};uint32_t* ps{};float* scratch{};
 size_t rb{};unsigned rows{},count{},experts{},split{};bool paired{},has_routes{},indirect{};
};
static_assert(sizeof(Bound)<=1024,"packet28 arguments exceed 1024 bytes");
template<class F> F checked(F f){static_assert(sizeof(F)<=1024,"packet28 kernel capture exceeds 1024 bytes");return f;}
void validate(ownrt::Device&,const std::vector<integrated::Matrix>&,const std::string&,bool,unsigned,bool indirect=false);
integrated::Launch submit(ownrt::Device&,const std::vector<integrated::Matrix>&,const std::string&,bool,unsigned,bool indirect=false);
}
