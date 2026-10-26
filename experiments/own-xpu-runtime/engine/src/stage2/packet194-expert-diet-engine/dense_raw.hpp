#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// OWNRT_DENSE_RAW=1 (lab 2026-10-26, default off): raw-size storage for the p33 dense Q6_K / Q8_0 weights (GSQ mode:
// the logits head, the gdn.qkv / gdn.z / qsa.qgate Q6_K sites and the attention-output Q8_0 sites). The default build
// stores them expanded (packet10-kopt5 expanded.hpp, variant 6): K int8 codes, one F32 scale word per 16 (Q6_K) / 32
// (Q8_0) columns and the retained block metadata, 1.320 / 1.1875 bytes per weight. Here a row holds exactly the GGUF
// bytes (0.8203 / 1.0625 bytes per weight), rearranged into planes so that a lane's columns are aligned word loads.
//
// Q6_K row (K % 512 == 0; block pair p = blocks 2p, 2p+1; 420 bytes per pair) in four planes:
//  L [K/2]   at 0        pair p, lane l: two 32-bit words at 256p+8l (block 2p, then 2p+1) with the low nibbles of the
//                        lane's 8 columns 256b+8l+j: byte i holds column i in its low and column 4+i in its high nibble.
//  H [K/4]   at K/2      pair p, lane l: two 16-bit words at K/2+128p+4l (block 2p, then 2p+1). With h' = high2 ^ 2 (the
//                        top two bits of the 6-bit two's complement of q = code - 32), column j's h' sits at bit
//                        6, 14, 2, 10, 4, 12, 0, 8 for j = 0..7.
//  S [K/16]  at 3K/4     pair p: 32 bytes at 3K/4+32p; sub-scale g of block 2p at 2g, of block 2p+1 at 2g+1.
//  D [K/128] at 13K/16   pair p: the fp16 d of block 2p, then of block 2p+1, at 13K/16+4p.
// Decoding forms, per column, the byte (q << 2) as int8, so float(int8) = 4q exactly, and
//   value = s4*float(4q), s4 = (half(d)*0.25f)*float(signed8(sc)).
// Q8_0 row (K % 256 == 0): C [K] the int8 codes in GGUF order, then D [K/16]: block b's fp16 d at K+2b;
//   value = half(d)*float(signed8(code)).
//
// Values. The expanded loader stores code = int8(q) and the scale word S = half(d)*float(signed8(sc)) (Q6_K; an
// 11-bit significand times an integer of magnitude <= 128: exact, s1_lanes.hpp) or S = half(d) (Q8_0), and the
// kernels form value = S*float(q). For Q6_K, half(d)*0.25f and its product with float(sc) are exact (|half(d)| >= 2^-24
// or 0, far above the F32 subnormal range), so s4 = S/4 exactly and s4*float(4q) rounds the same real number S*q:
// the same float, signed zeros included. iq3::half is the loader's conversion on the host; on the device it is the
// hardware conversion for every non-NaN half (the existing kopt half_scale contract) and the same software path for NaN.
// So every decoded value equals the stored expanded value bit for bit: check_rows() proves it per element at load,
// research/dense-raw/cputest/prove_dense_raw.cpp over every affected tensor of the model.
#include "stage2/packet2/kernels/math.hpp"
#include <bit>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <vector>
#if defined(__SYCL_DEVICE_ONLY__)
#include <sycl/sycl.hpp>
#endif
namespace denseraw {
using iq3::Type;
inline bool enabled(){static const bool on=[]{const char* e=std::getenv("OWNRT_DENSE_RAW");return e&&e[0]=='1';}();return on;}
// Load-time per-element proof (raw decode == expanded value), on with the switch unless OWNRT_DENSE_RAW_VERIFY=0.
inline bool verify(){static const bool on=[]{const char* e=std::getenv("OWNRT_DENSE_RAW_VERIFY");return !(e&&e[0]=='0');}();return on;}
inline bool supported(Type t,size_t k){return (t==Type::Q6_K&&k&&k%512==0&&k<=17408)||(t==Type::Q8_0&&k&&k%256==0&&k<=17408);}
inline size_t row_bytes(Type t,size_t k){
 if(!supported(t,k))throw std::invalid_argument("dense raw row geometry");
 return t==Type::Q6_K?k/256*210:k/32*34;
}
inline uint32_t load32(const uint8_t* p){
#if defined(__SYCL_DEVICE_ONLY__)
 return *reinterpret_cast<const uint32_t*>(p);
#else
 uint32_t v;std::memcpy(&v,p,4);return v;
#endif
}
inline uint32_t load16(const uint8_t* p){
#if defined(__SYCL_DEVICE_ONLY__)
 return *reinterpret_cast<const uint16_t*>(p);
#else
 return iq3::u16(p);
#endif
}
// fp16 bits -> float, the value of iq3::half for every input: on the device the hardware conversion for every non-NaN
// half, selected (never branched: d is per lane for Q8_0) against iq3::half's canonical quiet NaN.
inline float half_value(uint32_t h){
#if defined(__SYCL_DEVICE_ONLY__)
 const float hw=float(sycl::bit_cast<sycl::half>(uint16_t(h)));
 const float nan=iq3::bits_float(((h&0x8000u)<<16)|0x7f800000u|((h&1023u)?0x400000u:0u));
 return ((h>>10)&31u)==31u?nan:hw;
#else
 return iq3::half(h);
#endif
}
// Signed byte i of a 32-bit word as float (shift up, arithmetic shift down: the sign-extended byte, then its float).
inline float sbyte(uint32_t w,unsigned i){return float(int32_t(w<<(24-8*i))>>24);}
// ---- Q6_K ------------------------------------------------------------------------------------------------------
// The 8 values of one lane chunk from its low word, its 16-bit high word, its sub-scale and its block's d.
inline void q6_values(uint32_t low,uint32_t high,int sc,uint32_t d,float (&v)[8]){
 const float s4=(half_value(d)*0.25f)*float(sc);
 const uint32_t a=((low&0x0f0f0f0fu)<<2)|(high&0xc0c0u)|((high&0x0c0cu)<<20);        // byte i = q<<2 of column i
 const uint32_t c=((low&0xf0f0f0f0u)>>2)|((high&0x3030u)<<2)|((high&0x0303u)<<22);   // byte i = q<<2 of column 4+i
 #pragma unroll
 for(unsigned i=0;i<4;++i){v[i]=s4*sbyte(a,i);v[4+i]=s4*sbyte(c,i);}
}
// One block b, lane chunk l (columns 256b+8l..+7).
inline void q6_decode(const uint8_t* row,uint32_t k,uint32_t b,uint32_t l,float (&v)[8]){
 const uint32_t p=b/2u,o=b%2u;
 q6_values(load32(row+256u*p+8u*l+4u*o),load16(row+k/2u+128u*p+4u*l+2u*o),iq3::signed8(row[3u*(k/4u)+32u*p+2u*(l/2u)+o]),load16(row+13u*(k/16u)+4u*p+2u*o),v);
}
// Both blocks of pair p for lane l, as the kernels load them: 8 + 4 + 2 bytes per lane and one uniform 4-byte word.
struct Q6Pair {uint32_t low0,low1,high,sc,d;};
inline Q6Pair q6_load_pair(const uint8_t* row,uint32_t k,uint32_t p,uint32_t l){
 Q6Pair w;
#if defined(__SYCL_DEVICE_ONLY__)
 sycl::vec<uint32_t,2> lo;lo.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(row+256u*p+8u*l)));
 w.low0=lo[0];w.low1=lo[1];
#else
 w.low0=load32(row+256u*p+8u*l);w.low1=load32(row+256u*p+8u*l+4u);
#endif
 w.high=load32(row+k/2u+128u*p+4u*l);w.sc=load16(row+3u*(k/4u)+32u*p+2u*(l/2u));w.d=load32(row+13u*(k/16u)+4u*p);
 return w;
}
inline void q6_pair_values(const Q6Pair& w,unsigned o,float (&v)[8]){
 q6_values(o?w.low1:w.low0,o?w.high>>16:w.high&0xffffu,int(int8_t(uint8_t(o?w.sc>>8:w.sc))),o?w.d>>16:w.d&0xffffu,v);
}
// ---- Q8_0 ------------------------------------------------------------------------------------------------------
struct Q8Words {uint32_t lo,hi,d;};
inline Q8Words q8_load(const uint8_t* row,uint32_t k,uint32_t b,uint32_t l){
 const uint32_t tile=256u*b+8u*l;Q8Words w;
#if defined(__SYCL_DEVICE_ONLY__)
 sycl::vec<uint32_t,2> c;c.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint32_t*>(row+tile)));
 w.lo=c[0];w.hi=c[1];
#else
 w.lo=load32(row+tile);w.hi=load32(row+tile+4u);
#endif
 w.d=load16(row+k+2u*(8u*b+l/4u));return w;
}
inline void q8_values(const Q8Words& w,float (&v)[8]){
 const float scale=half_value(w.d);
 #pragma unroll
 for(unsigned j=0;j<8;++j)v[j]=scale*sbyte(j<4?w.lo:w.hi,j&3);
}
template<Type T> inline void decode8(const uint8_t* row,uint32_t k,uint32_t b,uint32_t l,float (&v)[8]){
 static_assert(T==Type::Q6_K||T==Type::Q8_0);
 if constexpr(T==Type::Q6_K)q6_decode(row,k,b,l,v);else q8_values(q8_load(row,k,b,l),v);
}
// ---- host: GGUF rows -> raw rows; per-element proof against the expanded rows -----------------------------------
inline void repack_row(Type t,size_t k,const uint8_t* src,uint8_t* dst){
 if(t==Type::Q8_0){const size_t nb=k/32;for(size_t b=0;b<nb;++b){std::memcpy(dst+32*b,src+34*b+2,32);dst[k+2*b]=src[34*b];dst[k+2*b+1]=src[34*b+1];}return;}
 static constexpr unsigned high_bit[8]{6,14,2,10,4,12,0,8};
 const size_t nb=k/256;std::memset(dst,0,nb*210);
 for(size_t b=0;b<nb;++b){const uint8_t* s=src+210*b;const size_t p=b/2,o=b%2;
  for(unsigned l=0;l<32;++l){uint32_t low=0,high=0;
   for(unsigned j=0;j<8;++j){const unsigned i=8*l+j;
    const unsigned lo=(s[(i/128)*64+i%64]>>(4*((i%128)/64)))&15,hi=(s[128+(i/128)*32+i%32]>>(2*((i%128)/32)))&3;
    low|=uint32_t(lo)<<(j<4?8*j:8*(j-4)+4);high|=uint32_t(hi^2u)<<high_bit[j];}
   std::memcpy(dst+256*p+8*l+4*o,&low,4);const uint16_t h=uint16_t(high);std::memcpy(dst+k/2+128*p+4*l+2*o,&h,2);}
  for(unsigned g=0;g<16;++g)dst[3*(k/4)+32*p+2*g+o]=s[192+g];
  dst[13*(k/16)+4*p+2*o]=s[208];dst[13*(k/16)+4*p+2*o+1]=s[209];}
}
inline std::vector<uint8_t> repack(Type t,const uint8_t* src,size_t bytes,size_t k){
 const size_t src_rb=k/iq3::layout(t).elements*iq3::layout(t).bytes,rb=row_bytes(t,k);
 if(!bytes||bytes%src_rb)throw std::invalid_argument("dense raw: whole source rows required");
 if(src_rb!=rb)throw std::logic_error("dense raw: row bytes differ from GGUF bytes");
 std::vector<uint8_t> out(bytes);for(size_t r=0;r<bytes/src_rb;++r)repack_row(t,k,src+r*src_rb,out.data()+r*rb);return out;
}
// Count of elements whose raw decode (both the per-block and the per-pair load paths) differs, as bits, from the
// expanded row value scale*float(signed8(code)).
inline uint64_t check_rows(Type t,const uint8_t* raw,const uint8_t* expanded,size_t rows,size_t k,size_t expanded_rb){
 const size_t rb=row_bytes(t,k);const unsigned group=t==Type::Q6_K?16:32;uint64_t bad=0;
 for(size_t r=0;r<rows;++r){const uint8_t* w=raw+r*rb;const uint8_t* e=expanded+r*expanded_rb;
  for(uint32_t tile=0;tile<k;tile+=8){const uint32_t b=tile/256,l=(tile%256)/8;float v[8],u[8];
   if(t==Type::Q6_K){decode8<Type::Q6_K>(w,uint32_t(k),b,l,v);q6_pair_values(q6_load_pair(w,uint32_t(k),b/2,l),b%2,u);}
   else {decode8<Type::Q8_0>(w,uint32_t(k),b,l,v);q8_values(q8_load(w,uint32_t(k),b,l),u);}
   const float scale=iq3::bits_float(iq3::u32(e+k+4*(tile/group)));
   for(unsigned j=0;j<8;++j){const uint32_t want=std::bit_cast<uint32_t>(scale*float(iq3::signed8(e[tile+j])));
    bad+=(want!=std::bit_cast<uint32_t>(v[j]))||(want!=std::bit_cast<uint32_t>(u[j]));}}}
 return bad;
}
} // namespace denseraw
