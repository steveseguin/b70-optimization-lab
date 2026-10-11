#pragma once
#include "math.hpp"
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace iq3 {
struct Fixture {
  Type type,activation,output_type;uint32_t columns,rows;
  std::vector<uint8_t> packed;std::vector<uint16_t> x;
  explicit Fixture(const std::string& path) {
    std::ifstream f(path,std::ios::binary);uint32_t header[5];f.read(reinterpret_cast<char*>(header),sizeof header);
    if(!f)throw std::runtime_error("fixture header");
    type=Type(header[0]);columns=header[1];rows=header[2];activation=Type(header[3]);output_type=Type(header[4]);
    auto l=layout(type);
    if(!l.elements || !columns || columns>16384 || columns%l.elements || !rows || rows>16 || (activation!=Type::F16 && activation!=Type::BF16) || (output_type!=Type::F16 && output_type!=Type::BF16))throw std::runtime_error("fixture extent");
    packed.resize(size_t(rows)*columns/l.elements*l.bytes);x.resize(columns);
    f.read(reinterpret_cast<char*>(packed.data()),packed.size());f.read(reinterpret_cast<char*>(x.data()),x.size()*2);
    char c;if(!f || f.get(c))throw std::runtime_error("fixture payload");
  }
  size_t row_bytes()const {return packed.size()/rows;}
  std::vector<float> decoded() const {
    std::vector<float> out(size_t(rows)*columns);for(size_t i=0;i<out.size();++i)out[i]=element(type,packed.data(),i);return out;
  }
  std::vector<float> gemv() const {
    std::vector<float> out(rows);for(unsigned r=0;r<rows;++r)out[r]=gemv_row(type,packed.data()+r*row_bytes(),x.data(),activation,columns);return out;
  }
};
}
