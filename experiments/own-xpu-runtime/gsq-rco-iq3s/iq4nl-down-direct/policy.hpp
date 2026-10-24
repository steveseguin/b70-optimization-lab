#pragma once
#include <cstddef>
#include <cstdint>
#include <stdexcept>
namespace gsq_iq4_direct {
// Numeric GGUF IDs keep this admission helper independent of device headers.
template<class Type,class Allocation>
inline void policy(Type t,uint32_t experts,uint32_t rows,size_t k,uint32_t count,
                   uint32_t span,Type activation,Type output,unsigned sg,Allocation fp32) {
  if(unsigned(t)!=20 || experts!=512 || rows!=2560 || k!=640 || count!=10 ||
     span!=2560 || unsigned(activation)!=30 || unsigned(output)!=30 || sg!=32 || fp32)
    throw std::invalid_argument("IQ4_NL direct down requires 512x2560x640/top10/span2560/BF16/SG32/no-FP32");
}
}
