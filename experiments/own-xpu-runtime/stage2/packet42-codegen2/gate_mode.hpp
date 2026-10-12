#pragma once
namespace p42gate {
#ifdef P42_BINDING_GATE
inline constexpr bool bindings_only=true;
#else
inline constexpr bool bindings_only=false;
#endif
}
#ifdef P42_BINDING_GATE
#define P42_DEVICE_EXECUTED "false"
#else
#define P42_DEVICE_EXECUTED "true"
#endif
