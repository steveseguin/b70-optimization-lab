#define OWN_RT_HOST_ONLY 1
#include "p49b_gemv.hpp"
static_assert(p49bgemv::layout(iq3::Type::IQ2_S,2560).row_bytes==820,"one-card IQ2_S K=2560 row stride");
static_assert(p49bgemv::layout(iq3::Type::IQ2_S,2560).halves==800,"one-card halves offset");
int main(){}
