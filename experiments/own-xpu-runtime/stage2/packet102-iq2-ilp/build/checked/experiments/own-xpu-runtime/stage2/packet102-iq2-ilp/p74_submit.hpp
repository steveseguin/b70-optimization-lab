#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/p74_submit.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/build/checked/experiments/own-xpu-runtime/stage2/packet102-iq2-ilp/p49c_submit.hpp"
namespace p74 {
integrated::Launch submit(ownrt::Device&,const integrated::Matrix&,unsigned variant,p39::Kind=p39::Kind::expert_checks,const p39::Bindings& = {});
}
