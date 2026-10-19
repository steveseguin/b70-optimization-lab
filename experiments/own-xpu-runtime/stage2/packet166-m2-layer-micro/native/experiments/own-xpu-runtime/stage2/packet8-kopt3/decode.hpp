#pragma once
#include "../packet7-kopt2/reference.hpp"
// Original scalar-index/block scheduling from local FORMAT.md. No external code.
namespace iq3::kopt3 {
// IQ4_XS is format-only here: absent from the production census and packet2 Type.
constexpr Type IQ4_XS=static_cast<Type>(23);
inline Layout format_layout(Type t){return t==IQ4_XS?Layout{256,136}:layout(t);}
inline constexpr int8_t iq4_levels[16]={-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
struct ConstantTables {
  uint64_t iq2(unsigned i)const{return iq2_s_grid[i];}
  uint32_t iq3s(unsigned i)const{return iq3_s_grid[i];}
  uint32_t iq3(unsigned i)const{return iq3_grid[i];}
  int iq4(unsigned i)const{return iq4_levels[i];}
};
struct HostShare {
  template<class F> auto operator()(unsigned owner,F f)const{return f(owner);}
};
// Each lane owns eight consecutive weights, unchanged from round2. A subgroup
// covers a whole 256-weight tile. Share evaluates metadata only at its owner.
// Scales belong to 16/32-weight subblocks, not the whole 256-weight block.
template<Type T,class Tables,class Share>
inline void decode8(const uint8_t* row,size_t k,float* v,Tables tables,Share share) {
  if constexpr(layout(T).elements==1 && T!=IQ4_XS) {
    for(unsigned j=0;j<8;++j)v[j]=element(T,row,k+j);
  } else {
    constexpr unsigned block=T==Type::Q8_0 || T==Type::IQ4_NL?32:256;
    constexpr unsigned bytes=T==IQ4_XS?136:layout(T).bytes;
    const auto b=row+(k/block)*bytes;unsigned i=k%block,lane=(k%256)/8;
    // For 32-weight formats each quartet of lanes owns one packed block.
    unsigned base_owner=block==32?(lane/4)*4:0;
    float d=share(base_owner,[&](unsigned){return half(u16(b+(T==Type::Q6_K?208:T==Type::Q3_K?108:0)));});
    float scale=d;unsigned signs=0;uint64_t grids[2]{};
    if constexpr(T==Type::IQ2_S) {
      scale=share(lane/2*2,[&](unsigned){unsigned s=(b[74+i/32]>>(4*((i/16)%2)))&15;return (d*(0.5f+float(s)))*0.25f;});
      unsigned q=i/8,ix=b[2+q]|(((b[66+q/4]>>(2*(q%4)))&3)<<8);
      grids[0]=tables.iq2(ix);signs=b[34+q];
    } else if constexpr(T==Type::IQ3_S) {
      scale=share(lane/4*4,[&](unsigned){return d*float(1+2*((b[106+i/64]>>(4*((i/32)%2)))&15));});
      signs=b[74+i/8];
      for(unsigned g=0;g<2;++g){unsigned q=i/4+g;grids[g]=tables.iq3s(b[2+q]|(((b[66+q/8]>>(q%8))&1)<<8));}
    } else if constexpr(T==Type::IQ3_XXS) {
      unsigned word=share(lane/4*4,[&](unsigned){return u32(b+66+4*(i/32));});
      scale=share(lane/4*4,[&](unsigned){return (d*(0.5f+float(word>>28)))*0.5f;});
      unsigned code=(word>>(7*((i%32)/8)))&127;signs=code|((std::popcount(code)%2)<<7);
      for(unsigned g=0;g<2;++g)grids[g]=tables.iq3(b[2+i/4+g]);
    } else if constexpr(T==Type::Q6_K) {
      scale=share(lane/2*2,[&](unsigned){return d*float(signed8(b[192+i/16]));});
    } else if constexpr(T==Type::Q3_K) {
      scale=share(lane/2*2,[&](unsigned){unsigned g=i/16;int sc=((b[96+g%8]>>(4*(g/8)))&15)|(((b[104+g%4]>>(2*(g/4)))&3)<<4);return d*float(sc-32);});
    } else if constexpr(T==IQ4_XS) {
      scale=share(lane/4*4,[&](unsigned){unsigned g=i/32;int sc=((b[4+g/2]>>(4*(g%2)))&15)|(((u16(b+2)>>(2*g))&3)<<4);return d*float(sc-32);});
    }
    #pragma unroll
    for(unsigned j=0;j<8;++j) {
      unsigned n=i+j;int16_t q=0;
      if constexpr(T==Type::IQ2_S || T==Type::IQ3_S || T==Type::IQ3_XXS) {
        int mag=T==Type::IQ2_S?int((grids[0]>>(8*j))&255):int((grids[j/4]>>(8*(j%4)))&255);
        q=int16_t((signs>>j)&1?-mag:mag);
      } else if constexpr(T==Type::Q6_K) {
        int lo=(b[(n/128)*64+n%64]>>(4*((n%128)/64)))&15;
        int hi=(b[128+(n/128)*32+n%32]>>(2*((n%128)/32)))&3;q=int16_t((lo|(hi<<4))-32);
      } else if constexpr(T==Type::Q3_K) {
        q=int16_t(((b[32+(n/128)*32+n%32]>>(2*((n%128)/32)))&3)-4*(1-((b[n%32]>>(n/32))&1)));
      } else if constexpr(T==Type::Q8_0)q=int16_t(signed8(b[2+n]));
      else if constexpr(T==Type::IQ4_NL)q=int16_t(tables.iq4((b[2+n%16]>>(4*(n/16)))&15));
      else if constexpr(T==IQ4_XS)q=int16_t(tables.iq4((b[8+(n/32)*16+n%16]>>(4*((n%32)/16)))&15));
      // One quant -> FP32 conversion. Nonzero IQ magnitudes make sign folding
      // exact for finite scales, including signed zero. Preserve NaN sign via
      // the old magnitude-then-sign equation on exceptional scale encodings.
      if constexpr(T==Type::IQ2_S || T==Type::IQ3_S || T==Type::IQ3_XXS) {
        if((std::bit_cast<uint32_t>(scale)&0x7fffffff)>0x7f800000)
          v[j]=(scale*float(q<0?-q:q))*float(q<0?-1:1);
        else v[j]=scale*float(q);
      } else v[j]=scale*float(q);
    }
    // Do not return before broadcasts: a 32-weight-format tile can mix finite
    // and exceptional scales across lane quartets. Every lane participates.
    if constexpr(T!=IQ4_XS) {
      if((std::bit_cast<uint32_t>(d)&0x7f800000)==0x7f800000)
        for(unsigned j=0;j<8;++j)v[j]=element(T,row,k+j);
    }
  }
}
template<Type T,class Tables,class Share>
inline float dot(const uint8_t* w,const uint16_t* x,Type a,size_t begin,size_t end,unsigned lane,Tables tables,Share share) {
  float sum=0;
  // Uniform tile loop: every lane executes broadcasts, including raw tails.
  for(size_t tile=begin;tile<end;tile+=256) {
    size_t k=tile+lane*8;float values[8]{},inputs[8]{};
    #pragma unroll
    for(unsigned j=0;j<8;++j)if(k+j<end)inputs[j]=a==Type::BF16?bits_float(uint32_t(x[k+j])<<16):half(x[k+j]);
    if constexpr(layout(T).elements==1) {
      for(unsigned j=0;j<8;++j)if(k+j<end)values[j]=element(T,w,k+j);
    } else {
      // Quant rows are whole blocks. A partial 256 tile is only possible for
      // 32-weight blocks: inactive lanes use a safe block but still broadcast.
      decode8<T>(w,k<end?k:tile,values,tables,share);
    }
    #pragma unroll
    for(unsigned j=0;j<8;++j)if(k+j<end){float product=values[j]*inputs[j];sum=sum+product;}
  }
  return sum;
}
}
