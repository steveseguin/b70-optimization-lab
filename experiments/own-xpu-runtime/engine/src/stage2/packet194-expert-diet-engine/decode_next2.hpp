#pragma once
// OWNRT_DECODE_NEXT2 (lab 2026-10-26, default off): exact decode-step changes after OWNRT_DECODE_NEXT. "1" enables
// xxs,hcgate,bf16split; otherwise a comma list of tokens:
//  xxs        routed IQ3_XXS gate/up at the block sites: packed logical lanes in 32-lane subgroups (work-item t of a row
//             owns lanes 4t..4t+3: one grid word, sign code and scale factor for four lanes), grid in work-group memory
//             (dn2_kernels.hpp, block.hpp).
//  hcgate     dense BF16 decode rows with K <= 1024 and >= 2048 rows (HC gate): 2 rows per subgroup instead of 4
//             (dense_v2::bf16_multi<2,4>).
//  bf16split  dense BF16 decode rows with 1024 < K < 8192 (router + shared gate, GDN a+b, QSA iq+ik): a row's 32
//             logical lanes over two 16-lane subgroups, the last tree level through work-group memory
//             (dense_v2::bf16_split<10,4>). HC low (K 10240) keeps bf16_multi<1,8>.
// Each output keeps its float operation sequence; see research/decode-next2/RESULT.md.
#include <cstdlib>
#include <string>
namespace decode_next2 {
inline const std::string& list() {
  static const std::string v=[]{const char* e=std::getenv("OWNRT_DECODE_NEXT2");const std::string s=e?e:"";return s=="1"?std::string("xxs,hcgate,bf16split"):s;}();
  return v;
}
inline bool enabled(const char* token) {
  const auto& v=list();if(v.empty()||v=="0")return false;
  return (","+v+",").find(std::string(",")+token+",")!=std::string::npos;
}
}
