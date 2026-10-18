// Actual production-shape recurrence, differently poisoned spare banks.
#define main inherited_p82_fixture_main
#include "p82_cpu.cpp"
#undef main
int main(){try{
 unsigned cases=0;size_t bytes=0;
 for(unsigned scenario:{0u,5u,6u,7u,8u,9u})for(bool packed:{false,true}){
  Data reference(1,scenario);ng::Shape s{};s.op=ng::gdn;s.tokens=1;s.capacity=4096;s.flags=2|8|(packed?4:0);
  Data expected=reference;p82brec::Kernel<true> k;k.shape=s;k.run(expected.args(false).p);
  std::array<std::vector<uint16_t>,3> banks;
  for(int active=0;active<3;++active)for(int spare=0;spare<3;++spare)if(active!=spare){
   Data actual=reference;
   for(int bank=0;bank<3;++bank)banks[bank].assign(786432,uint16_t(0x1234+bank*0x321));
   banks[active]=reference.input;const auto untouched=banks[3-active-spare];
   auto a=actual.args(false);a.p[5]=banks[active].data();a.p[7]=banks[spare].data();k.run(a.p);
   actual.state=banks[spare];check(actual.bytes()==expected.bytes(),"different destination changed production recurrence bytes");
   check(banks[active]==reference.input&&banks[3-active-spare]==untouched,"read-only bank changed");
   bytes+=actual.bytes().size();++cases;
  }
 }
 std::cout<<"{\"passed\":true,\"cases\":"<<cases<<",\"bytes_compared\":"<<bytes<<",\"physical_pairs\":6,\"state_elements\":786432}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
