#pragma once
#include "../expanded.hpp"
#include <fstream>
#include <string>
struct ExpandedCase {
 iq3::Type type;unsigned k,rows;std::vector<uint8_t> packed,expected;std::vector<float> values;
 explicit ExpandedCase(const std::string& path){std::ifstream f(path,std::ios::binary);uint32_t h[6];f.read(reinterpret_cast<char*>(h),sizeof h);if(!f)throw std::runtime_error("case header");
  type=iq3::Type(h[0]);k=h[1];rows=h[2];auto l=iq3::expanded::source_layout(type);
  if(!l.elements || !rows || rows>64 || k>17408 || k%l.elements || h[3]!=size_t(k)*rows/l.elements*l.bytes || h[4]!=rows*iq3::expanded::row_bytes(type,k) || h[5]!=size_t(k)*rows*4)throw std::runtime_error("case extent");
  packed.resize(h[3]);expected.resize(h[4]);values.resize(size_t(k)*rows);
  f.read(reinterpret_cast<char*>(packed.data()),h[3]);f.read(reinterpret_cast<char*>(expected.data()),h[4]);f.read(reinterpret_cast<char*>(values.data()),h[5]);char tail;if(!f || f.get(tail))throw std::runtime_error("case bytes");
 }
};
