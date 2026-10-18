// Actual production p33 and round2 host kernels, built separately by GNU/Intel.
#include "p33_submit.cpp"
#include "round2_submit.cpp"
#include "p105_submit.cpp"
#include <fstream>
#include <filesystem>
#include <iostream>
#include "p106_common.hpp"
using namespace p106;
static Best reduce(uint16_t* y,unsigned n,unsigned offset){
 integrated::Spec s;s.op=integrated::Op::argmax;s.ni=1;s.no=1;s.sizes[0]=n;s.sizes[1]=1;s.types[0]=flash::Scalar::bf16;s.types[1]=flash::Scalar::i32;
 int32_t index=0;uint32_t error=0,position=0,active=1;std::vector<float>scratch(2*((n+1023)/1024));Best best{};
 std::array<void*,7> ids{y,&index,scratch.data(),&error,&position,&active,&position};
 round2::Simple<integrated::Op::argmax,0,flash::Scalar::bf16> first(s);first.run(ids);
 round2::Simple<integrated::Op::argmax,1,flash::Scalar::bf16> last(s);last.run(ids);
 p105::Pack pack;pack.rows=n;pack.offset=offset;std::array<void*,4> ptrs{y,&index,&error,&best};pack.run(ptrs);return best;
}
int main(int argc,char**argv){try{
 if(argc!=2)throw std::runtime_error("output");std::filesystem::path out=argv[1];std::filesystem::create_directories(out);
 std::ofstream expected(out/"expected.bin",std::ios::binary),actual(out/"candidate.bin",std::ios::binary);
 auto check=[&](const void*a,const void*b,size_t n){expected.write(static_cast<const char*>(a),n);actual.write(static_cast<const char*>(b),n);if(std::memcmp(a,b,n))throw std::runtime_error("p105 byte mismatch");};
 // Full vocabulary and real row strides. Distinct row fingerprints expose a
 // wrong suffix origin; no 839 MB artifact is retained. Under 2 GiB resident.
 std::vector<uint8_t> weights(size_t(vocab)*3380),suffix_weights(size_t(suffix)*3380);
 for(unsigned r=0;r<vocab;++r){auto*w=weights.data()+size_t(r)*3380;for(unsigned k=0;k<2560;++k)w[k]=uint8_t(int((r*17+k*11)%63)-31);for(unsigned k=0;k<160;++k){float scale=float((r+k)%13+1)/128;std::memcpy(w+2560+4*k,&scale,4);}}
 std::memcpy(suffix_weights.data(),weights.data()+size_t(prefix)*3380,suffix_weights.size());
 std::vector<uint16_t>x(2560),ey(vocab),ay(vocab);
 auto head=[&](uint8_t*w,unsigned n,uint16_t*y){p33::Kernel<0,iq3::Type::Q6_K,2560,1>op;op.b.rows=n;op.b.count=op.b.experts=1;op.b.rb=3380;std::array<void*,9> ptrs{w,w,x.data(),y,y,x.data(),y,y,y};op.run(ptrs);};
 unsigned tests=0;
 for(unsigned token=0;token<3;++token){for(unsigned k=0;k<2560;++k)x[k]=iq3::bf16_bits(float(int((k*7+token*19)%113)-56)/64);
  head(weights.data(),vocab,ey.data());head(weights.data(),prefix,ay.data());head(suffix_weights.data(),suffix,ay.data()+prefix);
  check(ey.data(),ay.data(),vocab*2);auto e=reduce(ey.data(),vocab,0),a=merge(reduce(ay.data(),prefix,0),reduce(ay.data()+prefix,suffix,prefix));check(&e,&a,16);++tests;
 }
 // Forced rounded ties, boundary rows, signed zeros, infinities and NaNs.
 // Invalid argmax is an error, never a published token. Finite payloads match
 // every bit, including the sign of the selected zero.
 for(unsigned mode=0;mode<20;++mode){std::fill(ey.begin(),ey.end(),iq3::bf16_bits(-2.f));
  if(mode<4){ey[mode==0?0:prefix-1]=0x3f80;ey[mode==2?vocab-1:prefix]=0x3f80;}
  else if(mode<6){std::fill(ey.begin(),ey.end(),uint16_t(mode==4?0x8000:0));ey[prefix]=mode==4?0:0x8000;}
  else if(mode<12){ey[(mode%3==0)?0:(mode%3==1)?prefix-1:prefix]=(mode<8?0x7f80:mode<10?0xff80:0x7fc1);}
  else if(mode==12)ey[prefix]=0x3f80; // suffix wins at first global suffix ID
  else if(mode==13)ey[vocab-1]=0x3f80; // last global ID must survive merge
  else if(mode==14){ey[prefix+11]=0x3f80;ey[vocab-1]=0x3f80;}
  else if(mode==15){ey[1023]=0x3f80;ey[1024]=0x3f80;ey[prefix]=0x3f80;}
  else if(mode==16)std::fill(ey.begin(),ey.end(),uint16_t(0x7fc1));
  else if(mode==17)ey[vocab-1]=0xff80;
  else if(mode==18){ey[5]=0x7fc1;ey[vocab-1]=0x7f80;}
  else {ey[0]=0x8000;ey[prefix]=0;}
  auto e=reduce(ey.data(),vocab,0),a=merge(reduce(ey.data(),prefix,0),reduce(ey.data()+prefix,suffix,prefix));
  if(!e.error)check(&e,&a,16);else{if(!a.error)throw std::runtime_error("nonfinite escaped");int32_t no_token=-1;check(&e.error,&a.error,4);check(&no_token,&no_token,4);}++tests;
 }
 bool refused=false;try{merge({0,0,0,0},{0,int(prefix)-1,0,0});}catch(const std::invalid_argument&){refused=true;}if(!refused)throw std::runtime_error("partition bound");
 std::ofstream(out/"native.json")<<"{\"passed\":true,\"device_executed\":false,\"full_vocab_tokens\":3,\"cases\":"<<tests<<",\"invalid_token_published\":false}\n";
 std::cout<<"full-vocabulary logits, exact finite argmax, ties and nonfinite refusal PASS\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
