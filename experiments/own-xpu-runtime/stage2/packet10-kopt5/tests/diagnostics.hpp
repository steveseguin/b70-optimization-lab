#pragma once
#include "../../packet9-kopt4/tests/expert_case.hpp"
#include <cmath>
#include <iomanip>
#include <sstream>

namespace expanded_test {
// Keep the actual bits in the native error receipt, before shutdown frees them.
inline std::string difference(const void* actual,const void* expected,size_t bytes,unsigned width) {
 const auto a=static_cast<const uint8_t*>(actual),e=static_cast<const uint8_t*>(expected);
 size_t first=0;while(first<bytes && a[first]==e[first])++first;
 if(first==bytes)return {};
 size_t index=first/width;uint32_t ab=0,eb=0;
 std::memcpy(&ab,a+index*width,width);std::memcpy(&eb,e+index*width,width);
 std::ostringstream out;out<<" byte_offset="<<first<<" element="<<index
   <<" actual_bits=0x"<<std::hex<<std::setfill('0')<<std::setw(width*2)<<ab
   <<" expected_bits=0x"<<std::setw(width*2)<<eb<<std::dec;
 if(width==4){float av=iq3::bits_float(ab),ev=iq3::bits_float(eb);
  out<<std::setprecision(17)<<" actual="<<av<<" expected="<<ev;
  if(std::isfinite(av)&&std::isfinite(ev))out<<" delta="<<(double(av)-double(ev));
  else out<<" delta=nonfinite";
 }
 return out.str();
}
struct Buffers:expert_test::Buffers {
 using expert_test::Buffers::Buffers;
 void equal(ownrt::Allocation from,const void* p,size_t n,const std::string& label) {
  expert_test::require(!expert_test::stopping,"cooperative stop before readback");
  auto h=slab(label,n);expert_test::wait(d,copy.copy(h,0,from,0,n,{}));
  unsigned width=label.find("BF16")!=std::string::npos || label=="rounded"?2:4;
  auto detail=difference(d.arena.row(h).pointer,p,n,width);
  if(!detail.empty())throw expert_test::ExactnessFailure("device/CPU byte mismatch: "+prefix+"/"+label+detail);
 }
};
}
