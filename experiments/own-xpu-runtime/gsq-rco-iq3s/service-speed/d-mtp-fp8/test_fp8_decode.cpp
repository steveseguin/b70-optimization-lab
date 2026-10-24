#include <cstdint>
#include <cstring>
#include <cmath>
#include <cstdio>
#include <stdexcept>
namespace iq3{inline float bits_float(uint32_t b){float f;std::memcpy(&f,&b,4);return f;}}
// engine host decode (mtp.hpp)
inline float fp8(uint8_t b){unsigned e=(b>>3)&15,m=b&7;if(e==15&&m==7)throw std::runtime_error("nonfinite official draft FP8");float x=e?float(8+m)*std::ldexp(1.f,int(e)-10):float(m)*std::ldexp(1.f,-9);return b&128?-x:x;}
// new kernel decode (mtp_kernels.cpp copy)
inline float fp8_value(uint8_t b){uint32_t e=(b>>3)&15,m=b&7;float x=e?iq3::bits_float(((e+120)<<23)|(m<<20)):float(m)*0x1p-9f;return b&128?-x:x;}
int main(){int bad=0,n=0;for(int k=0;k<256;++k){if((k&127)==127)continue;++n;float a=fp8(k),b=fp8_value(k);uint32_t x,y;std::memcpy(&x,&a,4);std::memcpy(&y,&b,4);if(x!=y){++bad;printf("code %d: %08x vs %08x\n",k,x,y);}
 // independent: value = (-1)^s * 2^(e-7) * (1+m/8), subnormal 2^-6*(m/8)
 int s=k>>7,e=(k>>3)&15,m=k&7;double ref=e?std::ldexp(1.0+m/8.0,e-7):std::ldexp(m/8.0,-6);if(s)ref=-ref;if((double)b!=ref||std::signbit(b)!=(bool)s){++bad;printf("ref %d\n",k);}}
 printf("codes %d mismatches %d max %g\n",n,bad,(double)fp8_value(126));return bad;}
