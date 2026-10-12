#pragma once
#include <stdexcept>
// Reserved dispatch extension: no packet39 code or callable implementation.
namespace packet38 {
inline constexpr bool routed_status_epilogue_qualified=false;
inline void require_status_epilogue_disabled(bool requested) {
 if(requested)throw std::invalid_argument("packet39 status epilogue is not qualified in packet38");
}
}
