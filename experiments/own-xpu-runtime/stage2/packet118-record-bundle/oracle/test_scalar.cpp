#include "../../packet47-qsa-attn/qsa_reference.hpp"
#include "split32_scalar.hpp"
#include <iostream>
int main(){int checks=0;
 for(int ctx:{1,31,32,33,129,1027,2051,4099})for(int rows:{1,2}){
  if(ctx<rows)continue;
  p47ref::Fixture fixture(ctx,rows,73);auto a=fixture.args();auto s=fixture.shape;
  std::vector<float> ref(size_t(rows)*24*256);p47ref::cpu_split(s,a,ref.data());
  for(int r=0;r<rows;++r)for(int h=0;h<24;++h){int n=p47ref::count(s,a,r);
   auto got=p49oracle::split32(n,256,[&](int j){return p47ref::score(s,a,r,h,j);},[&](int j,int d){return a.b(3,(a.i(4)[r*2051+j]*2+h/12)*256+d);});
   for(int d=0;d<256;++d){if(std::bit_cast<uint32_t>(got[d])!=std::bit_cast<uint32_t>(ref[(r*24+h)*256+d]))throw std::runtime_error("scalar split reference mismatch");++checks;}
  }
 }
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"bitwise_pre_gate_values\":"<<checks<<"}\n";
}
