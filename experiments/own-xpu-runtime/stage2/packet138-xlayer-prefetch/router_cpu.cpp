// CPU-only replay of the unchanged packed F32 router and probability tie rule.
// Arithmetic is reused from the lab's production specification, not BLAS.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <numeric>
#include <vector>
#include "../packet8-kopt3/reference.hpp"
#include "../packet42-codegen2/route42.hpp"

static bool rank16(const uint16_t* logits,uint32_t* ids){
 float scratch[1088]{};uint32_t error=0,active=1;
 route42::Args a{};a.input=logits;a.input_type=flash::Scalar::bf16;
 a.scratch=scratch;a.error=&error;a.active=&active;a.n=512;a.top=16;
 for(unsigned i=0;i<32;++i)route42::phase<0,512,16>(a,i);
 if(error)return false;
 for(unsigned i=0;i<32;++i)route42::phase<1,512,16>(a,i);
 float den=route42::subtree<256>(32,0,[&](int j){return scratch[32+j];});
 std::array<float,512>prob;std::array<unsigned,512>order;
 for(unsigned j=0;j<512;++j){prob[j]=scratch[64+j]/den;order[j]=j;}
 std::sort(order.begin(),order.end(),[&](unsigned i,unsigned j){return prob[i]>prob[j]||(prob[i]==prob[j]&&i<j);});
 for(unsigned i=0;i<16;++i)ids[i]=order[i];return true;
}
extern "C" int p138_rank(const uint16_t* logits,uint32_t* ids){return rank16(logits,ids)?0:1;}
extern "C" int p138_router(const float* weights,const uint16_t* input,unsigned count,uint16_t* logits,uint32_t* ids){
 if(!count||count>4096)return 1;
 #pragma omp parallel for schedule(static) num_threads(4)
 for(unsigned item=0;item<count;++item){
  for(unsigned row=0;row<512;++row){
   float value=iq3::kopt3::row(iq3::Type::F32,reinterpret_cast<const uint8_t*>(weights+row*2560),input+item*2560,
      iq3::Type::BF16,2560,iq3::kopt3::Variant::constant_split4);
   logits[item*512+row]=iq3::bf16_bits(value);
  }
 }
 for(unsigned item=0;item<count;++item)if(!rank16(logits+item*512,ids+item*16))return 2;
 return 0;
}
// Independent existing production route body; test top-16 extension against its
// top-ten route, including rounded-probability ties and underflow.
extern "C" int p138_production_rank10(const uint16_t* logits,uint32_t* ids){
 float scratch[1088]{},weights[10]{};uint32_t error=0,active=1;
 route42::Args a{};a.input=logits;a.input_type=flash::Scalar::bf16;
 a.output[0]=ids;a.output_type[0]=flash::Scalar::u32;a.output[1]=weights;a.output_type[1]=flash::Scalar::f32;
 a.scratch=scratch;a.error=&error;a.active=&active;a.n=512;a.top=10;a.no=2;
 route42::host(a);return int(error);
}
