#pragma once
#include <string>
#include <stdexcept>
namespace packet24 {
inline int kernel_version=1;
inline void select(const std::string& s){if(s!="v1"&&s!="v2")throw std::invalid_argument("kernels must be v1 or v2");kernel_version=s=="v2"?2:1;}
}
