#pragma once
// OWNRT_DECODE_NEXT (lab 2026-10-26, default off): exact decode-step changes after OWNRT_EXPERTS_V2. "1" enables both;
// otherwise a comma list of tokens:
//  dense8  dense Q8_0 decode rows (the shared-expert down projection) with packed logical lanes (MultiplyQ8Packed);
//          dense Q6_K decode rows (shared-expert gate/up, QSA k/v) through MultiplyBlockRows<1> instead of the
//          local-memory Multiply (kopt gemv).
//  mix4    the HC mix with its four sigmoid terms on four lanes (native.cpp).
// Each output keeps its float operation sequence; see research/decode-next/RESULT.md.
#include <cstdlib>
#include <string>
namespace decode_next {
inline const std::string& list() {
  static const std::string v=[]{const char* e=std::getenv("OWNRT_DECODE_NEXT");const std::string s=e?e:"";return s=="1"?std::string("dense8,mix4"):s;}();
  return v;
}
inline bool enabled(const char* token) {
  const auto& v=list();if(v.empty()||v=="0")return false;
  return (","+v+",").find(std::string(",")+token+",")!=std::string::npos;
}
inline int variant(const char* name,int fallback) {const char* e=std::getenv(name);return e?std::atoi(e):fallback;}
}
