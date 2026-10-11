// CPU only; independent scalar decode and recursively specified tree oracle.
#include "fixture.hpp"
#include "../reference.hpp"
#include <algorithm>
#include <cstring>
#include <filesystem>
#include <iostream>
using namespace iq3;
namespace {
uint64_t values=0,rows=0,old_fp32_differences=0,old_output_differences=0,output_fingerprint=14695981039346656037ull;
void equal(float a,float b){output_fingerprint^=std::bit_cast<uint32_t>(a);output_fingerprint*=1099511628211ull;if(std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(b))throw std::runtime_error("FP32 bit mismatch");}
float tree(const std::vector<float>& v,size_t first,size_t n) {
  if(n==1)return v[first];
  float left=tree(v,first,n/2),right=tree(v,first+n/2,n/2);return left+right;
}
float oracle(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t columns,unsigned sg) {
  std::vector<float> lanes(sg,0.0f);
  for(unsigned lane=0;lane<sg;++lane)
    for(size_t chunk=lane*8;chunk<columns;chunk+=sg*8)
      for(size_t i=chunk;i<std::min(columns,chunk+8);++i) {
        float input=a==Type::BF16?bits_float(uint32_t(x[i])<<16):half(x[i]);
        float product=element(t,w,i)*input;lanes[lane]=lanes[lane]+product;
      }
  return tree(lanes,0,sg);
}
template<Type T> void decoded(const uint8_t* w,size_t columns) {
  for(size_t k=0;k+8<=columns;k+=8) {
    float v[8];kopt::decode8<T>(w,k,v);
    for(unsigned i=0;i<8;++i){equal(v[i],element(T,w,k+i));++values;}
  }
}
void check_decode8(Type t,const uint8_t* w,size_t n) {
#define CASE(T) case Type::T:decoded<Type::T>(w,n);break
  switch(t) {CASE(F32);CASE(F16);CASE(BF16);CASE(Q8_0);CASE(Q3_K);CASE(Q6_K);CASE(IQ3_XXS);CASE(IQ2_S);CASE(IQ3_S);CASE(IQ4_NL);}
#undef CASE
}
void exercise(const Fixture& f) {
  for(unsigned r=0;r<f.rows;++r)check_decode8(f.type,f.packed.data()+r*f.row_bytes(),f.columns);
  for(unsigned sg:{16u,32u})for(unsigned mutation:{0u,1u,2u}) {
    auto x=f.x;
    if(mutation==1)for(auto& v:x)v^=0x8000;
    if(mutation==2)for(size_t i=0;i<x.size();++i)x[i]=i%2?0x8000:0;
    for(unsigned r=0;r<f.rows;++r) {
      auto w=f.packed.data()+r*f.row_bytes();
      auto current=kopt::gemv_row(f.type,w,x.data(),f.activation,f.columns,sg);
      auto old=iq3::gemv_row(f.type,w,x.data(),f.activation,f.columns);
      old_fp32_differences+=std::bit_cast<uint32_t>(current)!=std::bit_cast<uint32_t>(old);
      old_output_differences+=output_bits(current,f.output_type)!=output_bits(old,f.output_type);
      equal(current,oracle(f.type,w,x.data(),f.activation,f.columns,sg));++rows;
      // Raw rows additionally exercise the bounded final group, including <8.
      if(layout(f.type).elements==1)for(size_t n:{size_t(1),size_t(7),size_t(9),size_t(f.columns-1)}) {
        if(n<=f.columns){equal(kopt::gemv_row(f.type,w,x.data(),f.activation,n,sg),oracle(f.type,w,x.data(),f.activation,n,sg));++rows;}
      }
    }
  }
}
}
int main(int argc,char** argv) {
  try {
    if(argc!=2)throw std::runtime_error("host-tests FIXTURE_DIR");
    std::vector<std::filesystem::path> paths;
    for(auto& p:std::filesystem::directory_iterator(argv[1]))if(p.path().extension()==".fixture")paths.push_back(p.path());
    std::sort(paths.begin(),paths.end());if(paths.size()!=27)throw std::runtime_error("expected 27 fixtures");
    for(auto& p:paths)exercise(Fixture(p.string()));
    bool rejected=false;try{kopt::gemv_row(Type::F32,nullptr,nullptr,Type::BF16,0,8);}catch(const std::invalid_argument&){rejected=true;}
    if(!rejected)throw std::runtime_error("invalid subgroup accepted");
    std::cout<<"{\"passed\":true,\"fixtures\":"<<paths.size()<<",\"decode_values\":"<<values<<",\"output_fingerprint_fnv1a\":"<<output_fingerprint<<",\"oracle_rows\":"<<rows<<",\"old_fp32_differences\":"<<old_fp32_differences<<",\"old_output_differences\":"<<old_output_differences<<",\"invalid_subgroup_rejected\":true}\n";
  }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
