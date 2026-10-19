#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet153-snapshot-host/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/mock_order.hpp"
#pragma once
#ifdef OWN_RT_HOST_ONLY
#include <cstdlib>
#include <numeric>
#include <random>
#include <algorithm>
#include <vector>
namespace packet24 {
template<class F> void mock_items(size_t n,F body){
 const char* seed=std::getenv("PACKET24_ORDER_SEED");
 if(!seed){for(size_t i=0;i<n;++i)body(i);return;}
 std::vector<size_t> order(n);std::iota(order.begin(),order.end(),0);
 std::mt19937 rng(unsigned(std::strtoul(seed,nullptr,10)));std::shuffle(order.begin(),order.end(),rng);
 for(auto i:order)body(i);
}
}
#endif
