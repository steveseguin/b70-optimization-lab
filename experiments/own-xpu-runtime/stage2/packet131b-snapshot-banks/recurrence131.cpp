// Actual production-shape recurrence, differently poisoned spare banks.
#include <sstream>
#define main inherited_p82_fixture_main
#include "p82_cpu.cpp"
#undef main
int main(){try{
 unsigned cases=0;size_t bytes=0;std::ostringstream transcript,case_rows;
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
   auto raw=actual.bytes();const auto digest=packet26::hash(raw.data(),raw.size());transcript<<digest<<'\n';bytes+=raw.size();
   // Diagnostic only, AFTER strict raw candidate/reference equality above:
   // locate inherited compiler differences in NaN payload propagation.
   auto nan_only=raw;unsigned nan_count=0;
   for(size_t j=0;j<(actual.state.size()+actual.y.size())*2;j+=2){
    uint16_t value;std::memcpy(&value,nan_only.data()+j,2);
    if((value&0x7f80)==0x7f80&&(value&0x7f)){value=0x7fc0;std::memcpy(nan_only.data()+j,&value,2);++nan_count;}
   }
   if(cases)case_rows<<',';
   case_rows<<"{\"scenario\":"<<scenario<<",\"packed\":"<<packed<<",\"active\":"<<active<<",\"spare\":"<<spare<<",\"sha256\":\""<<digest<<"\",\"nan_count\":"<<nan_count<<",\"nan_diagnostic_sha256\":\""<<packet26::hash(nan_only.data(),nan_only.size())<<"\"}";++cases;
  }
 }
 const auto raw=transcript.str();
 std::cout<<"{\"passed\":true,\"cases\":"<<cases<<",\"bytes_compared\":"<<bytes<<",\"physical_pairs\":6,\"state_elements\":786432,\"canonical_sha256\":\""<<packet26::hash(raw.data(),raw.size())<<"\",\"case_hashes\":["<<case_rows.str()<<"]}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
