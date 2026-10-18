// Full-shape small.ffn tuple versus the exact standalone r5 arithmetic.
#define main inherited_batch_fixture_main
#include "batch_fixture.cpp"
#undef main
#include "p30_small.hpp"
int main(int argc,char**argv){try{
 if(argc!=2)throw std::runtime_error("output prefix required");
 expected.open(std::string(argv[1])+"-expected.bin",std::ios::binary);
 actual.open(std::string(argv[1])+"-actual.bin",std::ios::binary);
 for(auto name:{"small.ffn.q6","small.ffn.q8"}){
  const auto shapes=p30::small::shapes(name);
  std::vector<std::vector<uint8_t>> w;
  for(auto s:shapes)w.push_back(weights(s.type,s.cols,s.rows));
  for(unsigned edge=0;edge<5;++edge)for(unsigned input_row=0;input_row<2;++input_row){
   std::vector<uint16_t>x(2560);inputs(x,input_row?(edge+1)%5:edge);
   std::vector<std::vector<uint16_t>> grouped(4),standalone(4);
   std::vector<p30::small::Bound> bound;
   for(unsigned i=0;i<4;++i){auto s=shapes[i];grouped[i].resize(s.rows);standalone[i].resize(s.rows);
    bound.push_back({w[i].data(),x.data(),grouped[i].data(),w[i].size(),x.size(),grouped[i].size()});}
   p30::small::cpu(name,bound,"rows4");
   for(unsigned i=0;i<4;++i){auto s=shapes[i];const auto variant=integrated::arithmetic::r5_variant(s.type,s.rows,s.cols,1,false);
    const auto stride=integrated::arithmetic::row_bytes(s.type,s.cols,variant);
    for(unsigned r=0;r<s.rows;++r)standalone[i][r]=iq3::bf16_bits(integrated::arithmetic::row(s.type,w[i].data()+r*stride,x.data(),s.cols,variant));
    same(grouped[i].data(),standalone[i].data(),s.rows*2,std::string(name)+":"+s.label);
   }
  }
 }
 std::cout<<"{\"passed\":true,\"byte_checks\":"<<checks<<",\"device_executed\":false,\"model_executed\":false}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
