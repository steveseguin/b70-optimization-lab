#pragma once
// Original packet17 arithmetic. IEEE binary32, round-to-nearest ties-to-even,
// gradual underflow, explicit fused operations; no double or platform libm.
#include <bit>
#include <cstdint>
#ifndef DETMATH_TRACE
#define DETMATH_TRACE(op,a,b) ((void)0)
#endif
namespace detmath {
inline constexpr char version[]="iq3-p17-detmath-v2";
inline uint32_t bits(float x){return std::bit_cast<uint32_t>(x);}
inline float value(uint32_t x){return std::bit_cast<float>(x);}
inline float fma(float a,float b,float c){return __builtin_fmaf(a,b,c);}
inline float div(float a,float b){DETMATH_TRACE(4,a,b);return a/b;}
inline float sqrt(float x){DETMATH_TRACE(2,x,0.f);return __builtin_sqrtf(x);}
inline float rsqrt_plain(float x){return div(1.f,sqrt(x));}
inline float rsqrt_barrier(float x){volatile uint32_t u=bits(sqrt(x));return div(1.f,value(u));}
inline float rsqrt_corrected(float x){
 // Exact integer quotient and ties-to-even rounding of 1/sqrt_RN(x).
 // For positive finite float x both sqrt_RN(x) and its reciprocal are normal.
 float root=sqrt(x);uint32_t u=bits(root),a=u&0x7fffffff;
 if(a>0x7f800000)return value(0x7fc00000);
 if(!a)return value((u&0x80000000)|0x7f800000);
 if(a==0x7f800000)return value(u&0x80000000);
 uint32_t m=(u&0x7fffff)|0x800000;int e=int(u>>23)-127;
 if(m==0x800000)return value(uint32_t(127-e)<<23);
 constexpr uint64_t numerator=uint64_t(1)<<47;
 uint32_t q=uint32_t(numerator/m);uint64_t rem=numerator-uint64_t(q)*m;
 if(2*rem>m || (2*rem==m && (q&1)))++q;
 int out_exp=126-e;
 if(q==0x1000000){q>>=1;++out_exp;}
 return value((uint32_t(out_exp)<<23)|(q&0x7fffff));
}
#ifndef DETMATH_RSQRT_MODE
#define DETMATH_RSQRT_MODE 1
#endif
inline float rsqrt(float x){
 DETMATH_TRACE(3,x,0.f);
#if DETMATH_RSQRT_MODE == 0
 return rsqrt_plain(x);
#elif DETMATH_RSQRT_MODE == 1
 return rsqrt_barrier(x);
#else
 return rsqrt_corrected(x);
#endif
}
struct Pair {float hi,lo;};
inline Pair sum(float a,float b){float s=a+b;float v=s-a;return {s,(a-(s-v))+(b-v)};}
inline Pair add(Pair a,Pair b){auto s=sum(a.hi,b.hi);return sum(s.hi,(s.lo+a.lo)+b.lo);}
inline Pair neg(Pair a){return {-a.hi,-a.lo};}
inline Pair mul(Pair a,Pair b){float p=a.hi*b.hi;float e=fma(a.hi,b.hi,-p);e=fma(a.hi,b.lo,e);e=fma(a.lo,b.hi,e);return sum(p,e);}
inline Pair quotient(Pair a,Pair b){float q=div(a.hi,b.hi);Pair r=add(a,neg(mul({q,0},b)));return sum(q,div(r.hi+r.lo,b.hi));}
inline float rounded(Pair a){return a.hi+a.lo;}
inline constexpr Pair ln2={0x1.62e43p-1f,-0x1.05c61p-29f};
inline float exp(float x){
 DETMATH_TRACE(0,x,0.f);
 uint32_t u=bits(x),a=u&0x7fffffff;
 if(a>0x7f800000)return value(0x7fc00000);
 if(x>=0x1.62e43p+6f)return value(0x7f800000);
 if(x<=-0x1.9fe36ap+6f)return 0.f;
 if(a<0x33000000)return 1.f;
 float nf=x*0x1.715476p+0f;
 int n=int(nf+(nf>=0?0.5f:-0.5f));
 Pair r=add({x,0},neg(mul({float(n),0},ln2)));
 // Taylor exp(r), |r| <= log(2)/2 plus one reduction rounding error.
 Pair p={0x1.1eed8e0000000p-29f,0x1.ff1b120000000p-54f};
 p=add({0x1.ae64560000000p-26f,0x1.fd51380000000p-52f},mul(r,p));
 p=add({0x1.27e4fc0000000p-22f,-0x1.10ec140000000p-47f},mul(r,p));
 p=add({0x1.71de3a0000000p-19f,0x1.55b1cc0000000p-45f},mul(r,p));
 p=add({0x1.a01a020000000p-16f,-0x1.7f97fa0000000p-42f},mul(r,p));
 p=add({0x1.a01a020000000p-13f,-0x1.7f97fa0000000p-39f},mul(r,p));
 p=add({0x1.6c16c20000000p-10f,-0x1.27d27e0000000p-35f},mul(r,p));
 p=add({0x1.1111120000000p-7f,-0x1.ddddde0000000p-32f},mul(r,p));
 p=add({0x1.5555560000000p-5f,-0x1.5555560000000p-30f},mul(r,p));
 p=add({0x1.5555560000000p-3f,-0x1.5555560000000p-28f},mul(r,p));
 p=add({0x1.0000000000000p-1f,0x0.0p+0f},mul(r,p));
 p=add({0x1.0000000000000p+0f,0x0.0p+0f},mul(r,p));
 p=add({1.f,0.f},mul(r,p));
 if(n <= -126){
  // Round once into the integer subnormal significand, avoiding double rounding.
  float scale=value(uint32_t(n+149+127)<<23);Pair t=mul(p,{scale,0});
  uint32_t k=uint32_t(t.hi);Pair rem=add(t,{-float(k),0});
  if(rem.hi>0.5f || (rem.hi==0.5f && (rem.lo>0.f || (rem.lo==0.f && (k&1)))))++k;
  return value(k);
 }
 if(n==128){p=mul(p,{2.f,0});n=127;}
 return rounded(p)*value(uint32_t(n+127)<<23);
}
inline float log(float x){
 DETMATH_TRACE(1,x,0.f);
 uint32_t u=bits(x),a=u&0x7fffffff;
 if(a>0x7f800000)return value(0x7fc00000);
 if(!a)return value(0xff800000);
 if(u>>31)return value(0x7fc00000);
 if(a==0x7f800000)return x;
 int e=0;
 if(a<0x800000){x=x*0x1p+23f;a=bits(x);e=-23;}
 e+=int(a>>23)-127;
 float m=value((a&0x7fffff)|0x3f800000);
 if(m>0x1.6a09e6p+0f){m=m*0.5f;++e;}
 Pair z=quotient({m-1.f,0},sum(m,1.f)),z2=mul(z,z);
 Pair p={0x1.8618620000000p-4f,-0x1.e79e7a0000000p-30f};
 p=add({0x1.af286c0000000p-4f,-0x1.af286c0000000p-31f},mul(z2,p));
 p=add({0x1.e1e1e20000000p-4f,-0x1.e1e1e20000000p-32f},mul(z2,p));
 p=add({0x1.1111120000000p-3f,-0x1.ddddde0000000p-28f},mul(z2,p));
 p=add({0x1.3b13b20000000p-3f,-0x1.89d89e0000000p-28f},mul(z2,p));
 p=add({0x1.745d180000000p-3f,-0x1.745d180000000p-28f},mul(z2,p));
 p=add({0x1.c71c720000000p-3f,-0x1.c71c720000000p-30f},mul(z2,p));
 p=add({0x1.24924a0000000p-2f,-0x1.b6db6e0000000p-27f},mul(z2,p));
 p=add({0x1.99999a0000000p-2f,-0x1.99999a0000000p-28f},mul(z2,p));
 p=add({0x1.5555560000000p-1f,-0x1.5555560000000p-26f},mul(z2,p));
 p=add({0x1.0000000000000p+1f,0x0.0p+0f},mul(z2,p));
 Pair l=mul(z,p);
 return rounded(add(mul({float(e),0},ln2),l));
}
inline float softplus(float x){return x<20.f?log(1.f+exp(x)):x;}
} // namespace detmath
