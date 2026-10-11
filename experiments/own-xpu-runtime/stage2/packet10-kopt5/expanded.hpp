#pragma once
#include "../packet8-kopt3/decode.hpp"
#include <cstring>
#include <vector>
// Our load-time transform. Normative grids retain packet1b's format-data credit.
namespace iq3::expanded {
constexpr Type IQ4_XS=static_cast<Type>(23);
inline Layout source_layout(Type t){return t==IQ4_XS?Layout{256,136}:layout(t);}
inline unsigned group_size(Type t){return t==Type::IQ2_S || t==Type::Q3_K || t==Type::Q6_K?16:32;}
inline unsigned metadata_size(Type t){
 switch(t){case Type::IQ2_S:case Type::IQ3_XXS:return 10;case Type::IQ3_S:return 6;
 case Type::Q3_K:return 14;case Type::Q6_K:return 18;default:return t==IQ4_XS?8:2;}
}
inline bool quantized(Type t){return source_layout(t).elements>1;}
inline size_t codes_size(Type t,size_t k){return t==Type::Q3_K?k/2:k;}
inline size_t row_bytes(Type t,size_t k){
 auto l=source_layout(t);
 if(!l.elements || !k || k%l.elements || k>17408)throw std::invalid_argument("expanded row geometry");
 return l.elements==1?k*l.bytes:codes_size(t,k)+4*(k/group_size(t))+(k/l.elements)*metadata_size(t);
}
inline int quant(Type t,const uint8_t* b,unsigned i){
 if(t==Type::Q8_0)return signed8(b[2+i]);
 if(t==Type::Q3_K)return ((b[32+(i/128)*32+i%32]>>(2*((i%128)/32)))&3)-4*(1-((b[i%32]>>(i/32))&1));
 if(t==Type::Q6_K)return (((b[(i/128)*64+i%64]>>(4*((i%128)/64)))&15)|(((b[128+(i/128)*32+i%32]>>(2*((i%128)/32)))&3)<<4))-32;
 if(t==Type::IQ4_NL)return kopt3::iq4_levels[(b[2+i%16]>>(4*(i/16)))&15];
 if(t==IQ4_XS)return kopt3::iq4_levels[(b[8+(i/32)*16+i%16]>>(4*((i%32)/16)))&15];
 unsigned mag=0,sign=0;
 if(t==Type::IQ2_S){unsigned j=i/8,ix=b[2+j]|(((b[66+j/4]>>(2*(j%4)))&3)<<8);mag=(iq2_s_grid[ix]>>(8*(i%8)))&255;sign=(b[34+j]>>(i%8))&1;}
 if(t==Type::IQ3_S){unsigned j=i/4,ix=b[2+j]|(((b[66+j/8]>>(j%8))&1)<<8);mag=(iq3_s_grid[ix]>>(8*(i%4)))&255;sign=(b[74+i/8]>>(i%8))&1;}
 if(t==Type::IQ3_XXS){unsigned w=u32(b+66+4*(i/32)),c=(w>>(7*((i%32)/8)))&127,mask=c|((std::popcount(c)%2)<<7);mag=(iq3_grid[b[2+i/4]]>>(8*(i%4)))&255;sign=(mask>>(i%8))&1;}
 return sign?-int(mag):int(mag);
}
inline float scale(Type t,const uint8_t* b,unsigned i){
 float d=half(u16(b+(t==Type::Q6_K?208:t==Type::Q3_K?108:0)));
 if(t==Type::IQ2_S)return (d*(0.5f+float((b[74+i/32]>>(4*((i/16)%2)))&15)))*0.25f;
 if(t==Type::IQ3_S)return d*float(1+2*((b[106+i/64]>>(4*((i/32)%2)))&15));
 if(t==Type::IQ3_XXS)return (d*(0.5f+float(u32(b+66+4*(i/32))>>28)))*0.5f;
 if(t==Type::Q6_K)return d*float(signed8(b[192+i/16]));
 if(t==Type::Q3_K){unsigned g=i/16;int s=((b[96+g%8]>>(4*(g/8)))&15)|(((b[104+g%4]>>(2*(g/4)))&3)<<4);return d*float(s-32);}
 if(t==IQ4_XS){unsigned g=i/32;int s=((b[4+g/2]>>(4*(g%2)))&15)|(((u16(b+2)>>(2*g))&3)<<4);return d*float(s-32);}
 return d;
}
inline void metadata(Type t,const uint8_t* b,uint8_t* dst){
 unsigned at=t==Type::Q6_K?208:t==Type::Q3_K?108:0;dst[0]=b[at];dst[1]=b[at+1];
 if(t==Type::IQ2_S)std::memcpy(dst+2,b+74,8);
 if(t==Type::IQ3_S)std::memcpy(dst+2,b+106,4);
 if(t==Type::Q3_K)std::memcpy(dst+2,b+96,12);
 if(t==Type::Q6_K)std::memcpy(dst+2,b+192,16);
 if(t==IQ4_XS)std::memcpy(dst+2,b+2,6);
 if(t==Type::IQ3_XXS)for(unsigned g=0;g<8;++g)dst[2+g]=u32(b+66+g*4)>>28;
}
inline std::vector<uint8_t> expand(Type t,const uint8_t* packed,size_t bytes,size_t k){
 auto rb=row_bytes(t,k);auto l=source_layout(t);size_t src_rb=k/l.elements*l.bytes;
 if(!bytes || bytes%src_rb)throw std::invalid_argument("whole source rows required");
 if(bytes/src_rb>SIZE_MAX/rb)throw std::overflow_error("expanded extent");
 std::vector<uint8_t> out(bytes/src_rb*rb,0);
 if(l.elements==1){std::memcpy(out.data(),packed,bytes);return out;}
 for(size_t r=0;r<bytes/src_rb;++r){auto dst=out.data()+r*rb;auto src=packed+r*src_rb;size_t cb=codes_size(t,k),sb=4*k/group_size(t);
  for(size_t i=0;i<k;++i){auto b=src+i/l.elements*l.bytes;int q=quant(t,b,i%l.elements);
   if(t==Type::Q3_K)dst[i/2]|=uint8_t((q&15)<<(4*(i%2)));else dst[i]=uint8_t(q);
   if(i%group_size(t)==0){float s=scale(t,b,i%l.elements);auto bits=std::bit_cast<uint32_t>(s);for(unsigned j=0;j<4;++j)dst[cb+4*(i/group_size(t))+j]=bits>>(8*j);}
   if(i%l.elements==0)metadata(t,b,dst+cb+sb+(i/l.elements)*metadata_size(t));
  }
 }
 return out;
}
inline float value(Type t,const uint8_t* row,size_t k,size_t i){
 if(source_layout(t).elements==1)return element(t,row,i);
 int q=t==Type::Q3_K?int((row[i/2]>>(4*(i%2)))&15):signed8(row[i]);
 if(t==Type::Q3_K && q>=8)q-=16;
 float s=bits_float(u32(row+codes_size(t,k)+4*(i/group_size(t))));
 // Preserve the original magnitude-then-sign NaN equation; finite sign folding
 // preserves every bit, including signed zero. No contraction anywhere.
 if((t==Type::IQ2_S || t==Type::IQ3_S || t==Type::IQ3_XXS) && (std::bit_cast<uint32_t>(s)&0x7fffffff)>=0x7f800000)
  return (s*float(q<0?-q:q))*float(q<0?-1:1);
 return s*float(q);
}
inline float lane(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t k,size_t begin,size_t end,unsigned l){
 float sum=0;
 for(size_t tile=begin+l*8;tile<end;tile+=256)for(unsigned j=0;j<8 && tile+j<end;++j){size_t i=tile+j;
  float input=a==Type::BF16?bits_float(uint32_t(x[i])<<16):half(x[i]);float prod=value(t,w,k,i)*input;sum=sum+prod;
 }
 return sum;
}
inline float row(Type t,const uint8_t* w,const uint16_t* x,Type a,size_t k,unsigned split){
 if(split!=1 && split!=4)throw std::invalid_argument("split");float part[4]{};
 for(unsigned s=0;s<split;++s){auto [lo,hi]=kopt2::bounds(k,s,split);float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=lane(t,w,x,a,k,lo,hi,l);part[s]=tree32(lanes);}
 return split==1?part[0]:(part[0]+part[1])+(part[2]+part[3]);
}
}
