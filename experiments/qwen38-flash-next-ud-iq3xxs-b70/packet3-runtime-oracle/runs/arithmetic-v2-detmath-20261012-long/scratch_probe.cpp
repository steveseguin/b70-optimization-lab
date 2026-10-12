// CPU-only allocation probe: no model, loader, device adapter or device discovery.
#include "core_v2.hpp"
#include <iostream>
#include <vector>
int main(){
  const size_t capacity=128ull*1024*1024;
  std::vector<float> scratch(capacity);
  std::cout<<"[";bool comma=false;
  for(int n:{8,600,1224,1225,2048,2049,2050,2051}){
    integrated::Core c;c.pool={scratch.data(),0,capacity};c.g.context=4096;c.op=integrated::Op::qsa_attention;
    size_t sizes[]={size_t(c.g.qh*c.g.ad),size_t(c.g.qh*c.g.ad),size_t(c.g.context*c.g.kvh*c.g.ad),size_t(c.g.context*c.g.kvh*c.g.ad),size_t(c.g.budget+3),1,1};
    for(int i=0;i<7;++i)c.inputs[i]=c.make(sizes[i]);
    c.outputs[0]=c.make(c.g.qh*c.g.ad);
    for(int i=0;i<c.g.budget+3;++i)c.inputs[4][i]=i<n?i:-1;
    c.run();if(c.failed||c.pool.failed)return 1;
    for(auto x:c.outputs[0])if(x!=0.f)return 2;
    std::cout<<(comma?",":"")<<"{\"admitted_positions\":"<<n<<",\"float_slots\":"<<c.pool.used<<",\"output_zero\":true}";comma=true;
  }
  std::cout<<"]\n";
}
