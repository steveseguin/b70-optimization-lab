#pragma once
// Packet100's tile16 permutation, extended to independently sized planes.
// Byte positions change; decode, scales, logical chains and trees do not.
#include "p100_down.hpp"
namespace p104 {
inline constexpr size_t offset(size_t row,size_t rb,size_t plane,size_t chunk,size_t at){
 return (row/16)*16*rb+plane*16+(at/chunk)*16*chunk+(row%16)*chunk+at%chunk;
}
inline const uint8_t* address(const uint8_t*w,size_t row,size_t rb,size_t plane,size_t chunk,size_t at){return w+offset(row,rb,plane,chunk,at);}
struct Plane {size_t start,bytes,chunk;};
inline std::vector<uint8_t> transpose(const uint8_t*src,size_t rows,size_t rb,std::initializer_list<Plane> planes){
 if(!src||!rows||rows%16||!rb)throw std::invalid_argument("p104 tile16 extent");
 size_t end=0;for(auto p:planes){if(p.start!=end||!p.chunk||p.bytes%p.chunk)throw std::invalid_argument("p104 plane coverage");end+=p.bytes;}
 if(end!=rb)throw std::invalid_argument("p104 plane extent");
 std::vector<uint8_t>dst(rows*rb);
 for(size_t r=0;r<rows;++r)for(auto p:planes)for(size_t k=0;k<p.bytes;k+=p.chunk)
  std::memcpy(dst.data()+offset(r,rb,p.start,p.chunk,k),src+r*rb+p.start+k,p.chunk);
 return dst;
}
template<bool HalfCache>inline std::vector<uint8_t> iq2(const uint8_t*src,size_t rows){
 constexpr size_t h=HalfCache?4:2,rb=800+10*h;
 return transpose(src,rows,rb,{{0,640,16},{640,80,2},{720,80,2},{800,10*h,h}});
}
template<unsigned K,bool Int8>inline const uint8_t* draft_address(const uint8_t*w,size_t row,size_t byte){
 constexpr size_t rb=Int8?K+K/16*4:K*2;
 if constexpr(Int8){if(byte>=K)return address(w,row,rb,K,4,byte-K);return address(w,row,rb,0,8,byte);}
 else return address(w,row,rb,0,16,byte);
}
template<unsigned K,bool Int8>inline std::vector<uint8_t> draft(const uint8_t*src,size_t rows){
 if constexpr(Int8)return transpose(src,rows,K+K/16*4,{{0,K,8},{K,K/16*4,4}});
 else return transpose(src,rows,K*2,{{0,K*2,16}});
}
inline std::vector<uint8_t> hc(const uint8_t*src,size_t rows){return transpose(src,rows,380,{{0,320,8},{320,40,4},{360,20,2}});}
inline std::vector<uint8_t> small_q6(const uint8_t*src,size_t rows){return transpose(src,rows,3380,{{0,2560,8},{2560,640,4},{3200,180,2}});}
inline std::vector<uint8_t> small_router(const uint8_t*src,size_t rows){return transpose(src,rows,10240,{{0,10240,32}});}
}
