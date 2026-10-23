#define OWN_RT_HOST_ONLY 1
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet193-expert-diet/native-pinned/checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x/p90_layout.hpp"
static_assert(p90::expert_stride(2560)==840,"two-card expanded row stride");
static_assert(p49bgemv::layout(iq3::Type::IQ2_S,2560).halves==800,"two-card halves offset");
int main(){}
