#pragma once
// OWNRT_EXPERTS_V2 (lab 2026-10-26): routed expert GEMVs with packed logical lanes (default off). "1" enables the
// verified set; otherwise a comma list of iq4nl,q20,iq4xs,guard,route,status,ew. Expert GEMVs: decode rows only (at most
// 32 slots per launch). guard: the active/error guard read once per subgroup or work-group instead of per item in
// CombineFast, GatherFast, RouteFast and the specialised body. route: two-level top-ten selection in RouteFast.
// status: the merged expert status check in one subgroup. ew: the generic element-wise ops (activation, mix,
// moe_combine) as plain per-item kernels (no team scratch or barriers; guard once per subgroup).
#include <cstdlib>
#include <string>
namespace experts_v2 {
// "1" = the verified set (every lever below; each is bitwise exact on the rank-1 gate).
inline bool enabled(const char* format) {
  static const std::string v=[]{const char* e=std::getenv("OWNRT_EXPERTS_V2");const std::string s=e?e:"";return s=="1"?std::string("iq4nl,q20,iq4xs,guard,route,status,ew"):s;}();
  if(v.empty()||v=="0")return false;
  return (","+v+",").find(std::string(",")+format+",")!=std::string::npos;
}
inline int variant(const char* name,int fallback) {
  const char* e=std::getenv(name);return e?std::atoi(e):fallback;
}
constexpr unsigned max_slots=32;
}
