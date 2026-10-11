// CPU only; independent scalar decode and recursively specified tree oracle.
#include "fixture.hpp"
#include "../reference.hpp"
#include "../../packet8-kopt3/dispatch.hpp"
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
float oracle(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t columns,kopt3::Variant v) {
  unsigned n=kopt3::splits(v);std::vector<float> parts(n);
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
    float v[8];kopt3::decode8<T>(w,k,v,kopt3::ConstantTables{},kopt3::HostShare{});
    for(unsigned i=0;i<8;++i){if(std::bit_cast<uint32_t>(v[i])!=std::bit_cast<uint32_t>(element(T,w,k+i)))std::cerr<<"decode type="<<unsigned(T)<<" k="<<k+i<<" actual="<<std::hex<<std::bit_cast<uint32_t>(v[i])<<" expected="<<std::bit_cast<uint32_t>(element(T,w,k+i))<<std::dec<<"\n";equal(v[i],element(T,w,k+i));++values;}
  }
}
void check_decode8(Type t,const uint8_t* w,size_t n) {
#define CASE(T) case Type::T:decoded<Type::T>(w,n);break
  switch(t) {CASE(F32);CASE(F16);CASE(BF16);CASE(Q8_0);CASE(Q3_K);CASE(Q6_K);CASE(IQ3_XXS);CASE(IQ2_S);CASE(IQ3_S);CASE(IQ4_NL);}
#undef CASE
}
void exercise(const Fixture& f) {
  for(unsigned r=0;r<f.rows;++r)check_decode8(f.type,f.packed.data()+r*f.row_bytes(),f.columns);
  for(auto variant:{kopt3::Variant::constant,kopt3::Variant::slm,kopt3::Variant::constant_split4,kopt3::Variant::slm_split4})for(unsigned mutation:{0u,1u,2u}) {
    auto x=f.x;
    if(mutation==1)for(auto& v:x)v^=0x8000;
    if(mutation==2)for(size_t i=0;i<x.size();++i)x[i]=i%2?0x8000:0;
    for(unsigned r=0;r<f.rows;++r) {
      auto w=f.packed.data()+r*f.row_bytes();
      auto current=kopt3::row(f.type,w,x.data(),f.activation,f.columns,variant);
      auto old=iq3::gemv_row(f.type,w,x.data(),f.activation,f.columns);
      old_fp32_differences+=std::bit_cast<uint32_t>(current)!=std::bit_cast<uint32_t>(old);
      old_output_differences+=output_bits(current,f.output_type)!=output_bits(old,f.output_type);
      equal(current,oracle(f.type,w,x.data(),f.activation,f.columns,variant));++rows;
      // Raw rows additionally exercise the bounded final group, including <8.
      if(layout(f.type).elements==1)for(size_t n:{size_t(1),size_t(7),size_t(9),size_t(f.columns-1)}) {
        if(n<=f.columns){equal(kopt3::row(f.type,w,x.data(),f.activation,n,variant),oracle(f.type,w,x.data(),f.activation,n,variant));++rows;}
      }
    }
  }
}
uint64_t special_decode_checks() {
 uint64_t checks=0;uint32_t rng=1979;
 const std::array<uint16_t,12> scales{0,0x8000,1,0x8001,0x3c00,0xbc00,0x7bff,0xfbff,0x7c00,0xfc00,0x7e00,0xfe00};
 for(auto t:{Type::IQ2_S,Type::IQ3_S,Type::IQ3_XXS,Type::Q3_K,Type::Q6_K,Type::IQ4_NL,Type::Q8_0}) {
  auto l=layout(t);std::vector<uint8_t> w(256/l.elements*l.bytes);
  for(auto h:scales)for(unsigned trial=0;trial<16;++trial) {
   for(auto& b:w){rng=rng*1664525u+1013904223u;b=uint8_t(rng>>24);}
   for(size_t off=0;off<w.size();off+=l.bytes){size_t at=off+(t==Type::Q3_K?108:t==Type::Q6_K?208:0);w[at]=h&255;w[at+1]=h>>8;}
   check_decode8(t,w.data(),256);checks+=256;
  }
 }
 // IQ4_XS is absent from the production census: independently test its format
 // equations without adding it to packet2 admission or device dispatch.
 for(unsigned trial=0;trial<256;++trial) {
  std::array<uint8_t,136> b{};
  for(auto& v:b){rng=rng*1664525u+1013904223u;v=uint8_t(rng>>24);}
  b[0]=0;b[1]=trial%2?0xbc:0x3c;
  for(unsigned k=0;k<256;k+=8){float v[8];kopt3::decode8<kopt3::IQ4_XS>(b.data(),k,v,kopt3::ConstantTables{},kopt3::HostShare{});
   for(unsigned j=0;j<8;++j){unsigned i=k+j,g=i/32;
    int sc=((b[4+g/2]>>(4*(g%2)))&15)|(((u16(b.data()+2)>>(2*g))&3)<<4);
    constexpr int levels[]{-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
    auto ix=(b[8+g*16+i%16]>>(4*((i%32)/16)))&15;
    float expected=(half(u16(b.data()))*float(sc-32))*float(levels[ix]);equal(v[j],expected);++checks;
   }
  }
 }
 return checks;
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
        for(auto v:{kopt3::Variant::constant,kopt3::Variant::slm,kopt3::Variant::constant_split4,kopt3::Variant::slm_split4}) {
          equal(kopt3::row(f.type,w.data(),x.data(),f.activation,columns,v),oracle(f.type,w.data(),x.data(),f.activation,columns,v));++extended_rows;
        }
      }
    }
    // Independent ordered sum oracle, adversarial cancellation and BF16 casts.
    uint64_t mixture_checks=0;
    for(unsigned trial=0;trial<64;++trial) {
      std::array<uint16_t,70> down{};std::array<float,10> weights{};
      for(unsigned slot=0;slot<10;++slot){weights[slot]=float(int((slot*7+trial)%19)-9)/16;
        for(unsigned r=0;r<7;++r)down[slot*7+r]=bf16_bits(float(int((slot*23+r*11+trial)%257)-128)/8);}
      for(unsigned r=0;r<7;++r){float expected=0;
        for(unsigned slot=0;slot<10;++slot){float product=bits_float(uint32_t(down[slot*7+r])<<16)*weights[slot];expected=expected+product;}
        equal(kopt4::combine(down.data(),weights.data(),7,r),expected);++mixture_checks;}
    }
    if(kopt4::work_groups(640,10,4,2)!=12800 || kopt4::work_groups(2560,10,1)!=6400 || kopt4::work_groups(5,10,1,2)!=40)throw std::runtime_error("work group counts");
    auto special_checks=special_decode_checks();
    kopt3::validate_aliases({{1,false},{1,false},{2,true}});
    for(const auto& bad:std::vector<std::vector<std::pair<uint64_t,bool>>>{{{1,true},{1,false}},{{1,false},{1,true}},{{1,true},{1,true}}}) {
      bool rejected_alias=false;try{kopt3::validate_aliases(bad);}catch(const std::invalid_argument&){rejected_alias=true;}
      if(!rejected_alias)throw std::runtime_error("writable alias accepted");
    }
    for(const auto& r:kopt3::dispatch_table)if(kopt3::dispatch_split4(r.type,r.rows,r.k,r.experts)!=r.split4)throw std::runtime_error("dispatch table");
    bool unknown=false;try{kopt3::dispatch_split4(99,1,1,1);}catch(const std::invalid_argument&){unknown=true;}
    if(!unknown)throw std::runtime_error("unknown dispatch accepted");
    bool rejected=false;try{kopt3::splits(static_cast<kopt3::Variant>(99));}catch(const std::invalid_argument&){rejected=true;}
    if(!rejected)throw std::runtime_error("invalid variant accepted");
    std::cout<<"{\"passed\":true,\"fixtures\":"<<paths.size()<<",\"mixture_checks\":"<<mixture_checks<<",\"extended_rows\":"<<extended_rows<<",\"special_decode_checks\":"<<special_checks<<",\"decode_values\":"<<values<<",\"output_fingerprint_fnv1a\":"<<output_fingerprint<<",\"oracle_rows\":"<<rows<<",\"old_fp32_differences\":"<<old_fp32_differences<<",\"old_output_differences\":"<<old_output_differences<<",\"invalid_variant_rejected\":true}\n";
  }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
