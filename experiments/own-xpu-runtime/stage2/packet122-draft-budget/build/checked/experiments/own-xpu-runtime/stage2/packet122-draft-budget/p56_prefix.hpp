#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/p56_prefix.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget/build/checked/experiments/own-xpu-runtime/stage2/packet122-draft-budget/p56_config.hpp"
#include <stdexcept>
namespace p56 {
inline unsigned rows(unsigned vocabulary, bool mini = false) {
 if (mini) return vocabulary; // Existing mini fixtures keep their own tiny vocabulary.
 if (vocabulary != full_rows) throw std::invalid_argument("packet56 vocabulary differs from sealed calibration");
 return prefix_rows;
}
template<class Matrix> void restrict_matrix(Matrix& m, unsigned n) {
 if (!n || n > m.rows || m.count != 1 || m.experts != 1 || m.routes)
  throw std::invalid_argument("packet56 prefix requires a contiguous non-routed head");
 m.rows=n; m.span=n; // Weight address, columns, variant and reduction tree are untouched.
}
template<class Spec> void restrict_argmax(Spec& s, unsigned n) {
 if (!n || n > s.sizes[0]) throw std::invalid_argument("packet56 argmax prefix bounds");
 s.sizes[0]=n; // Allocation remains full size; kernel cannot read stale suffix logits.
}
}
