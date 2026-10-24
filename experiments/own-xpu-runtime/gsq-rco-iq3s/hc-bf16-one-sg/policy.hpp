#pragma once
#include <cstddef>
#include <cstdint>
#include <stdexcept>
namespace gsq_hc_one_sg {
template<class Type,class Allocation>
inline void policy(Type t,size_t rows,size_t k,Type activation,Type output,unsigned sg,Allocation fp32) {
 if(unsigned(t)!=30 || (rows!=4&&rows!=320) || k!=10240 || unsigned(activation)!=30 || unsigned(output)!=30 || sg!=32 || fp32)
  throw std::invalid_argument("HC BF16 one-SG requires dense N4/N320 K10240 BF16 SG32 no-FP32");
}
}
