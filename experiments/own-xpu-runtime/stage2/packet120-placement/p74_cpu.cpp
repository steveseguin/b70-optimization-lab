#include "p49c_kernel.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
namespace fs=std::filesystem;
unsigned cases=0;uint64_t values=0;std::ofstream expected,actual,logfile;
void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
uint32_t rng=7400123;uint32_t random32(){rng^=rng<<13;rng^=rng>>17;return rng^=rng<<5;}
template<iq3::Type T,unsigned K,unsigned S,bool Attention=false>void test(){
 constexpr unsigned rows=17;constexpr auto E=Attention?p39::Kind::attention_combine:p39::Kind::expert_checks;
 for(unsigned trial=0;trial<4;++trial){
  size_t rb=p74::row_bytes(T,K);std::vector<uint8_t> packed(rows*rb);
  for(auto&b:packed)b=random32();
  const uint16_t scales[]={0,0x8000,1,0x8001,0x3b81,0xbb81,0x0400,0x8400,0x7bff,0xfbff};
  for(size_t block=0;block<packed.size()/iq3::layout(T).bytes;++block){auto off=block*iq3::layout(T).bytes+(T==iq3::Type::Q6_K?208:0);uint16_t h=scales[(block+trial)%10];std::memcpy(packed.data()+off,&h,2);}
  auto expanded=iq3::expanded::expand(T,packed.data(),packed.size(),K);auto er=iq3::expanded::row_bytes(T,K);
  std::vector<uint16_t>x(K),y0(rows,0xffff),y1(rows,0xffff),streams0(rows*4),streams1;
  for(auto&v:x)v=iq3::bf16_bits(float(int(random32()%33)-16)/16.f);for(auto&v:streams0)v=iq3::bf16_bits(float(int(random32()%33)-16)/16.f);streams1=streams0;
  uint32_t error=0,active=1,position=0;uint16_t inject[4]={0,0x3e80,0xbe80,0x3f80};std::vector<float>scratch0(rows*8),scratch1(rows*8);
  p39::Bound shape;shape.rows=rows;shape.rb=er;shape.capacity=4096;
  std::array<void*,19>a{expanded.data(),expanded.data(),x.data(),y0.data(),y0.data(),x.data(),y0.data(),y0.data(),scratch0.data(),x.data(),y0.data(),streams0.data(),inject,x.data(),x.data(),x.data(),&error,&active,&position};
  auto b=a;b[0]=packed.data();b[1]=packed.data();b[3]=y1.data();b[8]=scratch1.data();b[11]=streams1.data();
  p49c::DenseKernel<T,K,S,E> base;base.shape=shape;base.run(a);
  p49c::DenseKernel<T,K,S,E,0,true> candidate;shape.rb=rb;candidate.shape=shape;candidate.run(b);
  check(y0==y1,"operator BF16 mismatch");check(streams0==streams1,"attention tail mismatch");
  for(unsigned r=0;r<rows;++r){for(unsigned k=0;k<K;k+=8){float v[8];p74::decode8<T>(packed.data()+r*rb,k,v);for(unsigned j=0;j<8;++j){float ref=iq3::expanded::value(T,expanded.data()+r*er,K,k+j);check(std::bit_cast<uint32_t>(v[j])==std::bit_cast<uint32_t>(ref),"dequant bytes");++values;}}
   for(unsigned s=0;s<S;++s){auto range=iq3::kopt2::bounds(K,s,S);for(unsigned lane=0;lane<32;++lane){float a=p33::dense_lane<T,K>(expanded.data()+r*er,x.data(),range.first,range.second,lane),b=p74::lane<T,K>(packed.data()+r*rb,x.data(),range.first,range.second,lane);check(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b),"FP32 lane mismatch");expected.write((char*)&a,4);actual.write((char*)&b,4);}}
  }
  expected.write((char*)y0.data(),rows*2);actual.write((char*)y1.data(),rows*2);expected.write((char*)streams0.data(),rows*8);actual.write((char*)streams1.data(),rows*8);
  ++cases;logfile<<"{\"type\":"<<int(T)<<",\"columns\":"<<K<<",\"rows\":"<<rows<<",\"split\":"<<S<<",\"attention\":"<<Attention<<",\"trial\":"<<trial<<",\"passed\":true}\n";
 }
}
int main(int argc,char**argv){try{check(argc==2,"output directory");fs::path out=argv[1];fs::create_directories(out);expected.open(out/"expected.bin",std::ios::binary);actual.open(out/"candidate.bin",std::ios::binary);logfile.open(out/"cases.jsonl");
#define TEST(T,K) test<iq3::Type::T,K,1>();test<iq3::Type::T,K,4>()
 TEST(Q6_K,2560);TEST(Q8_0,2560);TEST(Q6_K,6144);TEST(Q8_0,6144);TEST(Q8_0,640);TEST(Q6_K,10240);TEST(Q8_0,10240);test<iq3::Type::Q6_K,6144,4,true>();
 std::ofstream(out/"native.json")<<"{\"passed\":true,\"cases\":"<<cases<<",\"dequant_values\":"<<values<<"}\n";std::cout<<cases<<" cases, "<<values<<" values PASS\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
