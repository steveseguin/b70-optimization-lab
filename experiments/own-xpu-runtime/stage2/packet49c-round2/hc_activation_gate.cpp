// CPU-only: include the real fixture constructors; dead owner/device runners
// are discarded at link time. No SYCL or Level Zero library is linked.
#include "adapter_fixture.cpp"
#include "p42_tiny.hpp"
#include "p39_fused.hpp"
#include <iostream>
__attribute__((noinline)) uint16_t core_activation(uint16_t v) {
 integrated::Core core;
 // Use the real Core operator, including its BF16 store.
 float memory[4]{}; core.pool={memory,0,4,0};core.op=integrated::Op::silu_div4;
 core.inputs[0]=core.make(1);core.inputs[0][0]=iq3::bits_float(uint32_t(v)<<16);
 core.run();return iq3::bf16_bits(core.outputs[0][0]);
}
__attribute__((noinline)) uint16_t kernel_activation(uint16_t v,int version) {
 ng::Shape sh{ng::activation,1,1};ng::Args a;uint16_t out=0;int32_t error=0,pos=0,active=1;
 a.p[0]=&v;a.p[2]=&out;a.p[15]=&error;a.p[17]=&pos;a.p[18]=&active;
 if(version==9)p42tiny::cpu<ng::activation,1>(sh,a);else ng::cpu(sh,a);
 return out;
}
int main(){
 unsigned checks=0,failures=0;auto cases=adapter_cases();
 if(cases.size()!=55)return 2;
 std::cout<<"{\"case_count\":55,\"hc_cases\":[";
 for(int index=51;index<55;++index){auto& c=cases[index];auto original=c.buffers;auto& site=c.sites[0];
  std::vector<float> scratch(1024);auto host=original;std::vector<void*> ptr;
  for(auto id:site.ids)ptr.push_back(host[id].data.data());
  ptr.insert(ptr.end(),{scratch.data(),host[c.error].data.data(),host[c.position].data.data(),host[c.active].data.data(),host[c.rope].data.data()});
  integrated::evaluate(site.spec,ptr.data());
  auto error=*reinterpret_cast<uint32_t*>(original[c.error].data.data());
  auto active=*reinterpret_cast<uint32_t*>(original[c.active].data.data());
  auto input=*reinterpret_cast<uint16_t*>(original[site.ids[0]].data.data());
  if(index>51)std::cout<<',';
  std::cout<<"{\"case\":"<<index<<",\"scenario\":"<<(index-51)<<",\"error\":"<<error<<",\"active\":"<<active<<",\"first_input\":"<<input<<",\"versions\":[0,1,9]}";
  for(int version:{0,1,9}){auto actual=original;ng::Args a;ng::Shape sh{ng::activation,1,320};
   a.p[0]=actual[site.ids[0]].data.data();a.p[2]=actual[site.ids[1]].data.data();a.p[15]=actual[c.error].data.data();a.p[17]=actual[c.position].data.data();a.p[18]=actual[c.active].data.data();
   if(version==9)p42tiny::cpu<ng::activation,1>(sh,a);else ng::cpu(sh,a);
   for(int id:c.outputs){++checks;if(actual[id].data!=host[id].data){++failures;std::cerr<<"adapter core mismatch case="<<index<<" version="<<version<<" buffer="<<id<<'\n';}}
   if(error||!active){++checks;if(actual[site.ids[1]].data!=original[site.ids[1]].data||actual[c.error].data!=original[c.error].data)++failures;}
  }
 }
 std::cout<<"],\"nan_payloads\":254";
 // A nonfinite unary input has a defined quieted payload, without asking the
 // compiler to select between two different NaN operands of a multiply.
 for(unsigned bits=0;bits<65536;++bits){if((bits&0x7fff)<=0x7f80)continue;
  auto want=uint16_t(bits|0x40);auto core=core_activation(bits);
  for(int version:{0,9,39}){auto actual=version==39?p39::hc_activation(bits):kernel_activation(bits,version);++checks;
   if(actual!=want||core!=want){++failures;if(bits==0x7fc1)std::cerr<<"payload 7fc1 version="<<version<<" actual="<<std::hex<<actual<<" core="<<core<<" expected="<<want<<std::dec<<'\n';}
  }
 }
 std::cout<<",\"checks\":"<<checks<<",\"failures\":"<<failures<<",\"passed\":"<<(failures?"false":"true")<<",\"device_executed\":false}\n";
 return failures?1:0;
}
