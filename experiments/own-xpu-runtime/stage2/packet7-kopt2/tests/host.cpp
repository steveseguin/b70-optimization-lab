// CPU only; independent scalar decode and recursively specified tree oracle.
#include "fixture.hpp"
#include "../reference.hpp"
#include <algorithm>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <set>
using namespace iq3;
namespace {
uint64_t values=0,rows=0,old_fp32_differences=0,old_output_differences=0,output_fingerprint=14695981039346656037ull;
void equal(float a,float b){output_fingerprint^=std::bit_cast<uint32_t>(a);output_fingerprint*=1099511628211ull;if(std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(b))throw std::runtime_error("FP32 bit mismatch");}
float tree(const std::vector<float>& v,size_t first,size_t n) {
  if(n==1)return v[first];
  float left=tree(v,first,n/2),right=tree(v,first+n/2,n/2);return left+right;
}
float oracle(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t columns,kopt2::Variant v) {
  unsigned n=kopt2::splits(v);std::vector<float> parts(n);
  for(unsigned s=0;s<n;++s) {
    // Independent scalar decode, recursive trees, independently derived tiles.
    size_t tiles=(columns+255)/256,lo=std::min(columns,(tiles*s/n)*256),hi=std::min(columns,(tiles*(s+1)/n)*256);
    std::vector<float> lanes(32,0.0f);
    for(unsigned l=0;l<32;++l)for(size_t chunk=lo+l*8;chunk<hi;chunk+=256)
      for(size_t i=chunk;i<std::min(hi,chunk+8);++i) {
        float input=a==Type::BF16?bits_float(uint32_t(x[i])<<16):half(x[i]);
        float product=element(t,w,i)*input;lanes[l]=lanes[l]+product;
      }
    parts[s]=tree(lanes,0,32);
  }
  return tree(parts,0,n);
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
  for(auto variant:{kopt2::Variant::split2,kopt2::Variant::split4,kopt2::Variant::wide32,kopt2::Variant::wide64})for(unsigned mutation:{0u,1u,2u}) {
    auto x=f.x;
    if(mutation==1)for(auto& v:x)v^=0x8000;
    if(mutation==2)for(size_t i=0;i<x.size();++i)x[i]=i%2?0x8000:0;
    for(unsigned r=0;r<f.rows;++r) {
      auto w=f.packed.data()+r*f.row_bytes();
      auto current=kopt2::row(f.type,w,x.data(),f.activation,f.columns,variant);
      auto old=iq3::gemv_row(f.type,w,x.data(),f.activation,f.columns);
      old_fp32_differences+=std::bit_cast<uint32_t>(current)!=std::bit_cast<uint32_t>(old);
      old_output_differences+=output_bits(current,f.output_type)!=output_bits(old,f.output_type);
      equal(current,oracle(f.type,w,x.data(),f.activation,f.columns,variant));++rows;
      // Raw rows additionally exercise the bounded final group, including <8.
      if(layout(f.type).elements==1)for(size_t n:{size_t(1),size_t(7),size_t(9),size_t(f.columns-1)}) {
        if(n<=f.columns){equal(kopt2::row(f.type,w,x.data(),f.activation,n,variant),oracle(f.type,w,x.data(),f.activation,n,variant));++rows;}
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
    // Larger K and uneven split boundaries: reuse packed blocks, never weights from another source.
    uint64_t extended_rows=0;
    std::set<Type> extended_types;
    for(auto& path:paths) {
      Fixture f(path.string());if(!extended_types.insert(f.type).second)continue;
      for(size_t columns:{size_t(256),size_t(768),size_t(5120),size_t(10240),size_t(17408)}) {
        const auto l=layout(f.type);std::vector<uint8_t> w(columns/l.elements*l.bytes);
        for(size_t i=0;i<w.size();++i)w[i]=f.packed[i%f.row_bytes()];
        std::vector<uint16_t> x(columns);for(size_t i=0;i<columns;++i)x[i]=f.x[i%f.x.size()];
        for(auto v:{kopt2::Variant::split2,kopt2::Variant::split4,kopt2::Variant::wide32,kopt2::Variant::wide64}) {
          equal(kopt2::row(f.type,w.data(),x.data(),f.activation,columns,v),oracle(f.type,w.data(),x.data(),f.activation,columns,v));++extended_rows;
        }
      }
    }
    // Enumerate every alignment residue and read footprint, with guard bytes.
    uint64_t footprints=0;
    for(unsigned bytes:{32u,64u})for(size_t offset=0;offset<bytes;++offset)
      for(size_t n:{size_t(1),size_t(18),size_t(34),size_t(82),size_t(98),size_t(110),size_t(210),size_t(820),size_t(1960),size_t(2200),size_t(10880)}) {
        alignas(64) std::array<uint8_t,11008> source{};std::vector<uint8_t> output(n+2,0xa5);
        for(size_t i=0;i<n;++i)source[offset+i]=uint8_t(i*71+offset);
        auto prefix=kopt2::stage_prefix(reinterpret_cast<uintptr_t>(source.data()+offset),n,bytes);
        auto vectors=(n-prefix)/bytes;
        if(vectors && (offset+prefix)%bytes)throw std::runtime_error("unaligned vector");
        for(unsigned lane=0;lane<32;++lane) {
          for(size_t i=lane;i<prefix;i+=32)output[1+i]=source[offset+i];
          for(size_t v=lane;v<vectors;v+=32)std::memcpy(output.data()+1+prefix+v*bytes,source.data()+offset+prefix+v*bytes,bytes);
          for(size_t i=prefix+vectors*bytes+lane;i<n;i+=32)output[1+i]=source[offset+i];
        }
        if(output.front()!=0xa5 || output.back()!=0xa5 || std::memcmp(output.data()+1,source.data()+offset,n))throw std::runtime_error("staging footprint");
        ++footprints;
      }
    uint64_t stream_checks=0;
    for(unsigned salt:{0u,97u})for(size_t words:{size_t(4),size_t(128),size_t(262144)}) {
      uint64_t actual=0,expected=0;
      for(size_t l=0;l<kopt2::stream_threads;++l){actual+=kopt2::stream_sum(words,l,salt);++stream_checks;}
      for(size_t i=0;i<words;++i)expected+=kopt2::stream_word(i,salt);
      if(actual!=expected)throw std::runtime_error("stream checksum");
    }
    bool rejected=false;try{kopt2::splits(static_cast<kopt2::Variant>(99));}catch(const std::invalid_argument&){rejected=true;}
    if(!rejected)throw std::runtime_error("invalid variant accepted");
    std::cout<<"{\"passed\":true,\"fixtures\":"<<paths.size()<<",\"extended_rows\":"<<extended_rows<<",\"vector_footprints\":"<<footprints<<",\"stream_lane_checks\":"<<stream_checks<<",\"decode_values\":"<<values<<",\"output_fingerprint_fnv1a\":"<<output_fingerprint<<",\"oracle_rows\":"<<rows<<",\"old_fp32_differences\":"<<old_fp32_differences<<",\"old_output_differences\":"<<old_output_differences<<",\"invalid_variant_rejected\":true}\n";
  }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
