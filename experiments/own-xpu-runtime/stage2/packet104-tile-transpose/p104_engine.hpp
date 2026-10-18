#pragma once
#include "p104_layout.hpp"
namespace p104 {
inline bool gate_tiled(std::string_view choice){auto c=p100::gate_choice(choice);return c=="gate-tile16"||c=="gate-halfcache-tile16";}
inline bool gate_cached(std::string_view choice){auto c=p100::gate_choice(choice);return c=="exp-halfcache"||c.ends_with("+halfcache")||c=="gate-halfcache-tile16";}
}
