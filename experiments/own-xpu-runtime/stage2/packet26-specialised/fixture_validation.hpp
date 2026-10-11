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
