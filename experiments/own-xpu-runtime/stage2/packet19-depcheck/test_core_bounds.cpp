// Standalone serial Core checks; host arithmetic only, no owner/device runtime.
#include "patched/packet4/core.hpp"
#include <iostream>
#include <limits>
static void check(bool good,const char* message){if(!good)throw std::runtime_error(message);}
struct Fixture {
 std::vector<float> memory=std::vector<float>(65536);integrated::Core c;
 Fixture(integrated::Op op,std::initializer_list<size_t> inputs,std::initializer_list<size_t> outputs){
  c.pool={memory.data(),0,memory.size(),0};c.g=integrated::Geometry::tiny();c.op=op;
  int j=0;for(auto n:inputs)c.inputs[j++]=c.make(n,.125f);
  j=0;for(auto n:outputs)c.outputs[j++]=c.make(n,0);
 }
};
int main(){int cases=0;
 for(float bad:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),1e30f,-2.f,.5f,8.f,1.f}){
  Fixture f(integrated::Op::qsa_attention,{16,16,32,32,11},{16});
  for(auto&v:f.c.in(4))v=-1;f.c.in(4)[0]=bad;f.c.run();
  check(f.c.failed==1,"Core attention must reject invalid/future selected id");++cases;
 }
 {Fixture f(integrated::Op::qsa_attention,{16,16,32,32,11},{16});
  for(auto&v:f.c.in(4))v=-1;f.c.in(4)[0]=0;f.c.run();check(!f.c.failed,"Core valid selected id");++cases;}
 for(int pos:{INT32_MIN,INT32_MAX,-1,8}){
  Fixture f(integrated::Op::qsa_select,{16,8},{11});f.c.position=pos;f.c.run();
  check(f.c.failed==1&&f.c.out(0)[0]==0,"Core select position clamps before indexing");++cases;
 }
 {Fixture f(integrated::Op::qsa_append_pool,{4,4,4},{32,32,32,8});
  f.c.position=INT32_MAX;f.c.run();check(f.c.failed==1&&f.c.out(0)[0]==.125f,"Core pool position clamps before address");++cases;}
 for(float bad:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),1e30f,-1.f,.5f,16.f}){
  Fixture f(integrated::Op::expert_gather,{10,16},{30,30,160});
  for(int j=0;j<10;++j)f.c.in(0)[j]=j;f.c.in(0)[0]=bad;f.c.run();
  check(f.c.failed==1&&f.c.out(0)[0]==0,"Core malformed route becomes safe zero");++cases;
 }
 std::cout<<"{\"cpu_only\":true,\"serial_core_index_cases\":"<<cases<<",\"passed\":true}\n";
}
