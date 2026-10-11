#include "detmath.hpp"
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <limits>
#include <initializer_list>
int main(){
 uint32_t cases[]={0,0x80000000,1,0x80000001,0x007fffff,0x00800000,0x3f800000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00001,0xffc00001,0x7f800001};
 for(auto b:cases){float x=detmath::value(b);printf("special %08x exp=%08x log=%08x rsqrt=%08x corrected=%08x\n",b,detmath::bits(detmath::exp(x)),detmath::bits(detmath::log(x)),detmath::bits(detmath::rsqrt_plain(x)),detmath::bits(detmath::rsqrt_corrected(x)));}
 uint64_t rsdiff=0, expbad=0,logbad=0,monobad=0;uint32_t seed=1234567,emax=0,lmax=0,ebits=0,lbits=0;
 for(int i=0;i<1000000;i++){
 seed=seed*1664525+1013904223;float x=detmath::value(seed);
 if(seed<0x7f800000 && seed>0){auto a=detmath::bits(detmath::rsqrt_plain(x)),b=detmath::bits(detmath::rsqrt_corrected(x));if(a!=b){if(rsdiff<10)printf("rsdiff %08x %08x %08x\n",seed,a,b);rsdiff++;}}
 if(std::isfinite(x)){
 float a=detmath::exp(x),b=(float)expl((long double)x);uint32_t ua=detmath::bits(a),ub=detmath::bits(b),d=ua>ub?ua-ub:ub-ua;if(d>emax){emax=d;ebits=seed;}if(d>1)expbad++;
 if(x>0){a=detmath::log(x);b=(float)logl((long double)x);ua=detmath::bits(a);ub=detmath::bits(b);d=ua>ub?ua-ub:ub-ua;if(d>lmax){lmax=d;lbits=seed;}if(d>1)logbad++;}
 }
 }
 // Full narrow regions straddling exp underflow, normal/subnormal, overflow.
 for(uint32_t center: {0xc2cff1b5u,0xc2aeac50u,0x42b17218u}){
 float prev=detmath::exp(detmath::value(center-65536));
 for(uint32_t u=center-65535;u<center+65536;u++){
 float x=detmath::value(u),a=detmath::exp(x),b=(float)expl((long double)x);uint32_t ua=detmath::bits(a),ub=detmath::bits(b),d=ua>ub?ua-ub:ub-ua;if(d>emax){emax=d;ebits=u;}if(d>1)expbad++;
 if((u>>31)?a>prev:a<prev)monobad++;prev=a;
 }
 }
 printf("summary rsdiff=%llu exp_max=%u at=%08x log_max=%u at=%08x exp_gt1=%llu log_gt1=%llu exp_boundary_monotonic_fail=%llu\n",(unsigned long long)rsdiff,emax,ebits,lmax,lbits,(unsigned long long)expbad,(unsigned long long)logbad,(unsigned long long)monobad);
 return (rsdiff || expbad || logbad || monobad) ? 1 : 0;
}