// Independent original host-only accuracy probe; long double is an oracle only.
#include "detmath.hpp"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <algorithm>
#include <cinttypes>
struct Stats { uint64_t tested=0, mismatch=0, over1=0, monotonic=0, specials_bad=0; uint32_t max_distance=0,worst_input=0,worst_got=0,worst_ref=0; long double max_ulp=0; };
static uint32_t rng=0x176acd91u;
uint32_t next(){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
void check(Stats &s,uint32_t bits,bool islog,bool adjacent=true){
 float x=detmath::value(bits),got=islog?detmath::log(x):detmath::exp(x);
 long double ref=islog?logl((long double)x):expl((long double)x);float rounded=(float)ref;s.tested++;
 if(std::isnan(ref)){if(!std::isnan(got))s.specials_bad++;return;}
 if(std::isinf(rounded)){if(got!=rounded)s.specials_bad++;return;}
 if(!std::isfinite(got)){s.specials_bad++;return;}
 uint32_t gb=detmath::bits(got),rb=detmath::bits(rounded);uint32_t dist=gb>rb?gb-rb:rb-gb;
 s.mismatch+=dist!=0;s.max_distance=std::max(s.max_distance,dist);
 long double spacing;
 if(fabsl(ref)<0x1p-126L)spacing=0x1p-149L;
 else {int e;frexpl(fabsl(ref),&e);spacing=ldexpl(1.L,e-24);}
 long double err=fabsl((long double)got-ref)/spacing;
 if(err>1.L)s.over1++;
 if(err>s.max_ulp){s.max_ulp=err;s.worst_input=bits;s.worst_got=gb;s.worst_ref=rb;}
 if(adjacent && std::isfinite(x)) {
   float after=std::nextafter(x,INFINITY),out=islog?detmath::log(after):detmath::exp(after);
   if(!std::isnan(out) && got>out)s.monotonic++;
 }
}
void emit(const char *name,const Stats&s){printf("\"%s\":{\"tested\":%" PRIu64 ",\"rounded_reference_differences\":%" PRIu64 ",\"max_integer_ulp_distance\":%u,\"max_true_ulp_error\":%.21Lg,\"above_one_true_ulp\":%" PRIu64 ",\"adjacent_monotonic_failures\":%" PRIu64 ",\"special_case_failures\":%" PRIu64 ",\"worst_input_bits\":\"%08x\",\"worst_output_bits\":\"%08x\",\"worst_rounded_reference_bits\":\"%08x\"}",name,s.tested,s.mismatch,s.max_distance,s.max_ulp,s.over1,s.monotonic,s.specials_bad,s.worst_input,s.worst_got,s.worst_ref);}
int main(int argc,char**argv){unsigned power=argc>1?unsigned(atoi(argv[1])):22;uint64_t n=uint64_t(1)<<power;Stats ex,lg;
 // Equal coverage of all exponent/sign classes, scrambled within bit strata.
 for(uint64_t i=0;i<n;++i){uint32_t b=uint32_t((i*(uint64_t(1)<<32))/n)+(next()&uint32_t((uint64_t(1)<<32)/n-1));check(ex,b,false);check(lg,b,true);}
 // Uniform real exp input, transition collars, dense log inputs around one.
 uint64_t dense=std::min(n,uint64_t(1)<<24);
 for(uint64_t i=0;i<dense;++i){float x=-104.f+(193.f*float(i))/float(dense);check(ex,detmath::bits(x),false);uint32_t b=0x3f000000u+uint32_t((i*0x1000000ull)/dense);check(lg,b,true);}
 for(uint32_t c:{0x42b17218u,0xc2cff1b5u,0xc2aeac50u,0x3f800000u,0x00800000u})for(int d=-4096;d<=4096;++d){check(ex,c+uint32_t(d),false);check(lg,c+uint32_t(d),true);}
 for(uint32_t b:{0u,0x80000000u,1u,0x80000001u,0x007fffffu,0x807fffffu,0x7f7fffffu,0xff7fffffu,0x7f800000u,0xff800000u,0x7fc00000u,0xffc00000u,0x7f800001u,0xff800001u}){check(ex,b,false);check(lg,b,true);}
 printf("{\"reference\":\"C++ long double expl/logl (host-only, worst vectors checked separately with Python Decimal precision 100)\",\"stratified_count\":%" PRIu64 ",\"definition\":\"absolute error divided by binary32 spacing in binade of exact value; subnormal spacing 2^-149\",",n);emit("exp",ex);printf(",");emit("log",lg);printf("}\n");return (ex.over1||lg.over1||ex.specials_bad||lg.specials_bad||ex.monotonic||lg.monotonic)?1:0;
}
