#include "dense.hpp"
#include "../packet26-specialised/arithmetic.hpp"
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

namespace {
using iq3::Type;
unsigned long long checks=0,classes=0,nan_pairs=0,current_nan_pairs=0;
enum class NanPolicy { exact, reference, current };
uint32_t rng(uint32_t& s){s=s*1664525u+1013904223u;return s;}
void equal(float a,float b,const char* label,NanPolicy policy=NanPolicy::exact) {
  ++checks;
  if(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b))return;
  if(policy!=NanPolicy::exact && std::isnan(a)&&std::isnan(b)){
    if(policy==NanPolicy::reference)++nan_pairs;else ++current_nan_pairs;return;
  }
  std::fprintf(stderr,"FAIL %s %08x != %08x check=%llu\n",label,
    std::bit_cast<uint32_t>(a),std::bit_cast<uint32_t>(b),checks);
  std::exit(1);
}

// Independent scalar reference uses the packed-format equation directly,
// never expanded::value or dense_lane. It preserves the registered lane tree.
template<Type T,unsigned K>
float reference(const uint8_t* packed,const uint16_t* x,unsigned split) {
  float parts[4]{};
  for(unsigned p=0;p<split;++p) {
    unsigned tiles=(K+255)/256;
    unsigned lo=std::min(K,(tiles*p/split)*256);
    unsigned hi=std::min(K,(tiles*(p+1)/split)*256);
    float sums[32]{};
    for(unsigned lane=0;lane<32;++lane)
      for(unsigned i=lo+lane*8;i<hi;i+=256)
        for(unsigned j=0;j<8 && i+j<hi;++j) {
          float value=iq3::element(T,packed,i+j);
          float input=iq3::bits_float(uint32_t(x[i+j])<<16);
          float product=value*input;
          sums[lane]=sums[lane]+product;
        }
    for(unsigned stride=1;stride<32;stride*=2)
      for(unsigned i=0;i<32;i+=2*stride)sums[i]=sums[i]+sums[i+stride];
    parts[p]=sums[0];
  }
  return split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]);
}

template<Type T,unsigned K>
void fixture(const char* name,unsigned production_rows) {
  ++classes;
  auto fmt=iq3::layout(T);
  auto v=integrated::arithmetic::r5_variant(T,production_rows,K,1,false);
  unsigned registered_split=v==1||v==4||v==7?4:1;
  constexpr uint16_t hs[]{0,0x8000,1,0x8001,0x03ff,0x83ff,0x7c00,0xfc00,0x7e01,0xfe03,0x3555,0xb555};
  constexpr uint16_t xs[]{0,0x8000,1,0x8001,0x007f,0x807f,0x7f80,0xff80,0x7fc1,0xffc3,0x3f80,0xbf80};
  constexpr uint32_t fs[]{0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x7f800000,0xff800000,0x7fc01234,0xffc05678,0x3f800000,0xbf800000};
  uint32_t state=0x31f24895u+K+unsigned(T);
  // Odd row counts exercise row offsets independently of a WG grouping.
  for(unsigned rows:{1u,3u,5u})for(unsigned mode=0;mode<15;++mode) {
    std::vector<uint8_t> packed(size_t(rows)*K/fmt.elements*fmt.bytes);
    for(auto& b:packed)b=uint8_t(rng(state)>>24);
    for(unsigned r=0;r<rows;++r)for(unsigned block=0;block<K/fmt.elements;++block) {
      auto b=packed.data()+(size_t(r)*K/fmt.elements+block)*fmt.bytes;
      unsigned which=mode?((mode-1)%12):10;
      if constexpr(T==Type::Q6_K || T==Type::Q8_0) {
        uint16_t h=mode?hs[which]:uint16_t(0x2000+(rng(state)%0x1200));
        unsigned at=T==Type::Q6_K?208:0;b[at]=uint8_t(h);b[at+1]=uint8_t(h>>8);
      } else if constexpr(T==Type::F32) {
        uint32_t f=mode?fs[which]:(0x3d000000u|(rng(state)&0x800fffffu));
        for(unsigned j=0;j<4;++j)b[j]=uint8_t(f>>(8*j));
      } else {
        uint16_t h=mode?(T==Type::BF16?xs[which]:hs[which]):uint16_t(0x3b00+rng(state)%0x200);
        b[0]=uint8_t(h);b[1]=uint8_t(h>>8);
      }
    }
    auto expanded=iq3::expanded::expand(T,packed.data(),packed.size(),K);
    auto rb=iq3::expanded::row_bytes(T,K);
    std::vector<uint16_t> x(K);
    for(unsigned i=0;i<K;++i)x[i]=mode>=13?xs[(i+mode)%12]:uint16_t(0x3b00+rng(state)%0x300);
    for(unsigned r=0;r<rows;++r) {
      auto w=expanded.data()+r*rb;
      auto src=packed.data()+size_t(r)*K/fmt.elements*fmt.bytes;
      // Both trees, including the exact production-selected tree.
      for(unsigned split:{registered_split,registered_split==1?4u:1u}) {
        float newer=p28::dense_row<T,K>(w,x.data(),split);
        float current=iq3::expanded::row(T,w,x.data(),Type::BF16,K,split);
        equal(newer,current,name,NanPolicy::current);
        equal(current,reference<T,K>(src,x.data(),split),name,NanPolicy::reference);
        equal(iq3::bits_float(uint32_t(iq3::bf16_bits(newer))<<16),
              iq3::bits_float(uint32_t(iq3::bf16_bits(current))<<16),name,NanPolicy::current);
      }
      // Deliberately unaligned ranges cross 16/32-weight scale boundaries.
      // Endpoints 255/257 and short last tiles guard shape-family boundaries.
      for(unsigned begin:{0u,1u,7u,15u,25u,31u}) {
        if(begin>=K)continue;
        for(unsigned end:{std::min(K,33u),std::min(K,255u),std::min(K,257u),K}) {
          if(end<begin)continue;
          for(unsigned lane=0;lane<32;++lane)
            equal(p28::dense_lane<T,K>(w,x.data(),begin,end,lane),
              iq3::expanded::lane(T,w,x.data(),Type::BF16,K,begin,end,lane),name,NanPolicy::current);
        }
      }
    }
  }
  if constexpr(T==Type::Q6_K || T==Type::Q8_0) {
    // Direct expanded-scale fixtures add true FP32 subnormals and payload NaNs
    // which cannot all originate from the model's FP16 block scale.
    constexpr unsigned group=T==Type::Q6_K?16:32;
    std::vector<uint8_t> w(iq3::expanded::row_bytes(T,K));
    std::vector<uint16_t> x(K,0x3f80);
    for(unsigned i=0;i<K;++i)w[i]=uint8_t(int(i%5)-2);
    for(auto scale_bits:fs) {
      for(unsigned g=0;g<K/group;++g)
        for(unsigned j=0;j<4;++j)w[K+4*g+j]=uint8_t(scale_bits>>(8*j));
      for(unsigned begin:{0u,7u,15u,31u})for(unsigned lane=0;lane<32;++lane) {
        if(begin>=K)continue;
        float ref=0;
        for(unsigned tile=begin+8*lane;tile<K;tile+=256)
          for(unsigned j=0;j<8 && tile+j<K;++j) {
            // Independent expanded-format reference, without original helper.
            int code=int(w[tile+j]);if(code>=128)code-=256;
            float value=iq3::bits_float(scale_bits)*float(code);
            float product=value*iq3::bits_float(uint32_t(x[tile+j])<<16);
            ref=ref+product;
          }
        float current=iq3::expanded::lane(T,w.data(),x.data(),Type::BF16,K,begin,K,lane);
        equal(p28::dense_lane<T,K>(w.data(),x.data(),begin,K,lane),current,name,NanPolicy::current);
        equal(current,ref,name,NanPolicy::reference);
      }
    }
  }
  std::printf("PASS dense %s type=%u rows=%u k=%u r5=%s\n",name,unsigned(T),production_rows,K,integrated::arithmetic::name(v));
}
}
int main() {
  fixture<Type::Q6_K,2560>("gdn.qkv.q6",10240);
  fixture<Type::Q8_0,2560>("gdn.qkv.q8.upgraded",10240);
  fixture<Type::Q6_K,2560>("gdn.z.q6",6144);
  fixture<Type::Q8_0,2560>("gdn.z.q8",6144);
  fixture<Type::Q6_K,2560>("qsa.qgate",12288);
  fixture<Type::Q6_K,2560>("qsa.k",512);
  fixture<Type::Q6_K,2560>("qsa.v",512);
  fixture<Type::Q6_K,6144>("attention.gdn",2560);
  fixture<Type::Q6_K,6144>("attention.qsa",2560);
  fixture<Type::Q6_K,2560>("logits",248320);
  fixture<Type::Q8_0,320>("hc.a.gate",10240);
  fixture<Type::Q8_0,320>("hc.f.gate",10240);
  fixture<Type::Q8_0,10240>("hc.a.low",320);
  fixture<Type::Q8_0,10240>("hc.f.low",320);
  fixture<Type::F32,10240>("hc.a.inject",4);
  fixture<Type::F32,10240>("hc.f.inject",4);
  fixture<Type::F32,4>("raw.short.row.boundary",10240);
  fixture<Type::F32,2560>("router",512);
  fixture<Type::Q8_0,2560>("shexpgate",640);
  fixture<Type::Q6_K,2560>("shexpgate.q6",640);
  fixture<Type::Q6_K,2560>("shexpup",640);
  fixture<Type::Q8_0,2560>("shexpup.q8",640);
  fixture<Type::Q8_0,640>("shexpdown",2560);
  fixture<Type::F32,2560>("shared_gate",1);
  fixture<Type::F32,2560>("gdn.a",48);
  fixture<Type::F32,2560>("gdn.b",48);
  fixture<Type::BF16,2560>("qsa.iq",512);
  fixture<Type::BF16,2560>("qsa.ik",128);
  fixture<Type::Q8_0,2560>("ple.key",10240);
  fixture<Type::Q8_0,2560>("ple.value",2560);
  fixture<Type::Q8_0,10240>("final.low",320);
  fixture<Type::Q8_0,320>("final.gate",10240);
  std::printf("{\"suite\":\"dense\",\"passed\":true,\"classes\":%llu,\"checks\":%llu,\"host_reference_nan_equivalence\":%llu,\"new_current_nan_encoding_differences\":%llu,\"strict_same_card_gate_pending\":true}\n",classes,checks,nan_pairs,current_nan_pairs);
  return 0;
}
