#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/fixture_validation.hpp"
#pragma once
#ifdef OWN_RT_HOST_ONLY
#include <device_validation.hpp>
#else
namespace fixture_validation { inline constexpr bool only=false; }
#endif
#include <stdexcept>
namespace fixture_validation {
struct InjectedFailure:std::invalid_argument {InjectedFailure():std::invalid_argument("injected CPU candidate mismatch"){}};
inline void inject_failure(const std::string& klass,bool candidate){
#ifdef OWN_RT_HOST_ONLY
 if(only&&inject&&candidate&&(klass=="norm"||klass=="streams"||klass=="gemv:gdn.qkv"))throw InjectedFailure();
#endif
}
}
